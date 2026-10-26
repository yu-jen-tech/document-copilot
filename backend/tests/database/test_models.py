"""Exercise model registration and PostgreSQL SQL without a database connection."""

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_mock_engine, func, insert, select
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.database.models import (
    Base,
    ChatMessage,
    ChatThread,
    DocumentChunk,
    MessageCitation,
    SourceDocument,
    User,
)


def test_models_import_without_credentials() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from app.database.models import Base; "
                "assert 'app.config' not in sys.modules; "
                "assert len(Base.metadata.tables) == 6"
            ),
        ],
        cwd=Path(__file__).resolve().parents[2],
        env={},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_schema_compiles_in_dependency_order_without_managing_auth() -> None:
    statements = []
    engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda statement, *args, **kwargs: statements.append(
            str(statement.compile(dialect=engine.dialect))
        ),
    )

    Base.metadata.create_all(engine)

    tables = [sql for sql in statements if sql.lstrip().startswith("CREATE TABLE")]
    names = [sql.split()[2] for sql in tables]
    assert set(names) == {
        "users",
        "source_documents",
        "document_chunks",
        "chat_threads",
        "chat_messages",
        "message_citations",
    }
    assert names.index("users") < names.index("chat_threads")
    assert names.index("source_documents") < names.index("document_chunks")
    assert names.index("chat_threads") < names.index("chat_messages")
    assert names.index("chat_messages") < names.index("message_citations")
    assert names.index("document_chunks") < names.index("message_citations")
    users = next(sql for sql in tables if "CREATE TABLE users" in sql)
    assert "REFERENCES auth.users (id) ON DELETE CASCADE" in users
    assert "gen_random_uuid()" not in users


def test_orm_relationships_link_history_to_source_evidence() -> None:
    configure_mappers()
    user = User(id=uuid4(), email="analyst@example.com")
    thread = ChatThread(user=user)
    message = ChatMessage(
        thread=thread, message_index=0, role="assistant", content="Revenue grew [1]."
    )
    document = SourceDocument()
    chunk = DocumentChunk(document=document)
    citation = MessageCitation(
        message=message, chunk=chunk, citation_index=1, excerpt="Revenue grew."
    )

    assert user.threads == [thread]
    assert thread.messages == [message]
    assert message.citations == [citation]
    assert citation.chunk.document is document
    assert document.chunks == [chunk]
    assert chunk.citations == [citation]


def test_search_vector_is_stored_and_generated_by_postgres() -> None:
    ddl = str(CreateTable(DocumentChunk.__table__).compile(dialect=dialect()))

    assert "VECTOR(1536) NOT NULL" in ddl
    assert (
        "TSVECTOR GENERATED ALWAYS AS "
        "(to_tsvector('english'::regconfig, content)) STORED NOT NULL"
    ) in ddl
    statement = insert(DocumentChunk).values(
        document_id=uuid4(),
        chunk_index=0,
        content="Revenue grew.",
        token_count=3,
        embedding=[0.0] * 1536,
    )
    sql = str(statement.compile(dialect=dialect()))
    assert "search_vector" not in sql
    assert "RETURNING document_chunks.id" in sql


def test_embedding_round_trips_as_a_list_of_floats() -> None:
    vector_type = DocumentChunk.__table__.c.embedding.type
    bind = vector_type.bind_processor(dialect())
    result = vector_type.result_processor(dialect(), None)
    embedding = [0.25, -0.5] + [0.0] * 1534

    assert result(bind(embedding)) == embedding


def test_models_support_separate_vector_and_keyword_search_queries() -> None:
    vector_query = (
        select(DocumentChunk.id)
        .order_by(DocumentChunk.embedding.cosine_distance([0.0] * 1536))
        .limit(10)
    )
    keywords = func.websearch_to_tsquery("english", "revenue growth")
    keyword_query = (
        select(DocumentChunk.id)
        .where(DocumentChunk.search_vector.bool_op("@@")(keywords))
        .order_by(func.ts_rank_cd(DocumentChunk.search_vector, keywords).desc())
        .limit(10)
    )

    assert "document_chunks.embedding <=>" in str(
        vector_query.compile(dialect=dialect())
    )
    sql = str(keyword_query.compile(dialect=dialect()))
    assert "document_chunks.search_vector @@ websearch_to_tsquery" in sql
    assert "ORDER BY ts_rank_cd" in sql


def test_citations_preserve_evidence_and_follow_message_deletions() -> None:
    ddl = str(CreateTable(MessageCitation.__table__).compile(dialect=dialect()))

    assert "REFERENCES chat_messages (id) ON DELETE CASCADE" in ddl
    assert "REFERENCES document_chunks (id) ON DELETE RESTRICT" in ddl
    assert "UNIQUE (message_id, citation_index)" in ddl
    assert MessageCitation.chunk.property.back_populates == "citations"
    assert DocumentChunk.citations.property.passive_deletes == "all"


def test_positions_are_unique_within_each_parent() -> None:
    chunk_ddl = str(CreateTable(DocumentChunk.__table__).compile(dialect=dialect()))
    message_ddl = str(CreateTable(ChatMessage.__table__).compile(dialect=dialect()))

    assert "UNIQUE (document_id, chunk_index)" in chunk_ddl
    assert "CHECK (chunk_index >= 0)" in chunk_ddl
    assert "UNIQUE (thread_id, message_index)" in message_ddl
    assert "CHECK (message_index >= 0)" in message_ddl
    assert "CHECK (role IN ('user', 'assistant'))" in message_ddl
