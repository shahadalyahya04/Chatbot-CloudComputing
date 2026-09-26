"""Offline behavior tests; Azure/Postgres/Chroma integration is checked on the VM.

Load only the storage functions through AST to avoid importing cloud/LLM clients
or reading the developer's .env. These tests use standard-library test doubles.
"""
import ast
import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlsplit
import uuid


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class ResourceNotFoundError(Exception):
    pass


def storage_functions():
    source = Path(__file__).resolve().parents[1] / 'backend.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    wanted = {'get_container', 'service_error', 'upload_pdf', 'load_chat', 'save_chat', 'delete_chat', 'health'}
    functions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
            node.decorator_list = []
            node.returns = None
            for arg in node.args.args:
                arg.annotation = None
            node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
            functions.append(node)
    namespace = dict(
        json=json, os=os, uuid=uuid, tempfile=tempfile, Path=Path,
        logging=logging, urlsplit=urlsplit, HTTPException=HTTPException,
        ResourceNotFoundError=ResourceNotFoundError, RealDictCursor=object,
        ContentSettings=lambda **kw: SimpleNamespace(**kw),
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(source), 'exec'), namespace)
    return namespace


class AzureStorageTests(unittest.TestCase):
    def setUp(self):
        self.ns = storage_functions()
        self.blob = MagicMock()
        self.container = MagicMock()
        self.container.get_blob_client.return_value = self.blob
        self.ns['get_container'] = lambda: self.container
        self.vector = MagicMock()
        self.ns['get_vectorstore'] = lambda: self.vector
        self.db = MagicMock()
        self.request = SimpleNamespace(
            chat_id='example', chat_name='Arabic chat',
            messages=[{'role': 'user', 'content': '\u0645\u0631\u062d\u0628\u0627'}],
            pdf_name=None, pdf_path=None, pdf_uuid=None,
        )

    def test_save_and_load_preserve_unicode_and_blob_reference(self):
        asyncio.run(self.ns['save_chat'](self.request, self.db))
        payload = self.blob.upload_blob.call_args.args[0]
        self.assertEqual(json.loads(payload), self.request.messages)
        self.db.commit.assert_called_once()
        sql, params = self.db.cursor.return_value.execute.call_args.args
        self.assertIn('ON CONFLICT (id)', sql)
        self.assertEqual(params[2], 'chat_logs/example.json')
        self.db.cursor.return_value.fetchall.return_value = [dict(
            id='example', name='Arabic chat', file_path=params[2],
            pdf_name=None, pdf_path=None, pdf_uuid=None,
        )]
        self.blob.download_blob.return_value.readall.return_value = payload
        records = asyncio.run(self.ns['load_chat'](self.db))
        self.assertEqual(records[0]['messages'], self.request.messages)

    def test_blob_failure_does_not_commit_and_redacts_signed_url(self):
        self.blob.upload_blob.side_effect = RuntimeError('https://example/?sig=SECRET')
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(self.ns['save_chat'](self.request, self.db))
        self.db.commit.assert_not_called()
        self.db.rollback.assert_called_once()
        self.assertNotIn('SECRET', caught.exception.detail)

    def configure_pdf(self, failing_loader=False):
        self.paths = []
        def loader(path):
            self.paths.append(path)
            self.assertEqual(Path(path).read_bytes(), b'%PDF-test-bytes')
            if failing_loader:
                raise ValueError('invalid PDF')
            return SimpleNamespace(load=lambda: ['document'])
        self.ns['PyPDFLoader'] = loader
        splitter = MagicMock()
        splitter.split_documents.return_value = [SimpleNamespace(page_content='document')]
        self.ns['RecursiveCharacterTextSplitter'] = lambda **kw: splitter
        return SimpleNamespace(content_type='application/pdf', filename='../../bad.pdf', read=AsyncMock(return_value=b'%PDF-test-bytes'))

    def test_pdf_uploads_bytes_and_removes_temporary_file(self):
        result = asyncio.run(self.ns['upload_pdf'](self.configure_pdf()))
        self.assertEqual(self.blob.upload_blob.call_args.args[0], b'%PDF-test-bytes')
        self.assertFalse(Path(self.paths[0]).exists())
        self.assertNotIn('..', result['pdf_path'])
        self.assertEqual(self.vector.add_texts.call_args.kwargs['metadatas'], [{'pdf_uuid': result['pdf_uuid']}])

    def test_bad_pdf_cleans_temporary_file_and_never_uploads(self):
        with self.assertRaises(HTTPException):
            asyncio.run(self.ns['upload_pdf'](self.configure_pdf(failing_loader=True)))
        self.assertFalse(Path(self.paths[0]).exists())
        self.blob.upload_blob.assert_not_called()

    def test_embedding_failure_cleans_blob_and_vectors(self):
        self.vector.add_texts.side_effect = RuntimeError('embedding failure')
        with self.assertRaises(HTTPException):
            asyncio.run(self.ns['upload_pdf'](self.configure_pdf()))
        self.blob.delete_blob.assert_called_once()
        self.vector.delete.assert_called_once()

    def test_delete_missing_chat_is_404(self):
        self.db.cursor.return_value.fetchone.return_value = None
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(self.ns['delete_chat'](self.request, self.db))
        self.assertEqual(caught.exception.status_code, 404)
        self.blob.delete_blob.assert_not_called()

    def test_container_uses_account_sas_without_manual_blob_url(self):
        ns = storage_functions()
        sdk = MagicMock()
        ns['BlobServiceClient'] = sdk
        with patch.dict(os.environ, {
            'AZURE_STORAGE_SAS_URL': 'https://account.blob.core.windows.net/?sig=a%2Bb&sp=rwdlc',
            'AZURE_STORAGE_CONTAINER': 'chatbot-files',
        }):
            ns['get_container']()
        self.assertEqual(sdk.call_args.kwargs['account_url'], 'https://account.blob.core.windows.net')
        self.assertEqual(sdk.call_args.kwargs['credential'], 'sig=a%2Bb&sp=rwdlc')
        sdk.return_value.get_container_client.assert_called_once_with('chatbot-files')


if __name__ == '__main__':
    unittest.main()
