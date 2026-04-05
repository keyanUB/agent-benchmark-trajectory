import io
import zipfile

from django.test import TestCase, Client


def make_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class ConvertViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_single_text_file(self):
        zip_bytes = make_zip({'hello.txt': 'Hello, world!'})
        response = self.client.post(
            '/convert',
            {'file': io.BytesIO(zip_bytes)},
            format='multipart'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'Hello, world!')

    def test_multiple_text_files(self):
        zip_bytes = make_zip({'a.txt': 'foo', 'b.txt': 'bar'})
        response = self.client.post(
            '/convert',
            {'file': io.BytesIO(zip_bytes)},
            format='multipart'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('foo', response.content.decode())
        self.assertIn('bar', response.content.decode())

    def test_no_file_returns_400(self):
        response = self.client.post('/convert')
        self.assertEqual(response.status_code, 400)

    def test_invalid_zip_returns_400(self):
        response = self.client.post(
            '/convert',
            {'file': io.BytesIO(b'not a zip file')},
            format='multipart'
        )
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        response = self.client.get('/convert')
        self.assertEqual(response.status_code, 405)