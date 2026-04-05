import io
import zipfile

from django.http import HttpResponse


def convert(request):
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return HttpResponse('No file provided', status=400)

    try:
        file_bytes = uploaded_file.read()
        zip_buffer = io.BytesIO(file_bytes)

        if not zipfile.is_zipfile(zip_buffer):
            return HttpResponse('Invalid zip file', status=400)

        zip_buffer.seek(0)
        text_parts = []

        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            for name in zf.namelist():
                info = zf.getinfo(name)
                if info.is_dir():
                    continue
                with zf.open(name) as f:
                    try:
                        content = f.read().decode('utf-8')
                        text_parts.append(content)
                    except (UnicodeDecodeError, ValueError):
                        # Skip non-text files
                        continue

        combined = ''.join(text_parts)
        return HttpResponse(combined, content_type='text/plain')

    except zipfile.BadZipFile:
        return HttpResponse('Invalid zip file', status=400)
    except Exception:
        return HttpResponse('Failed to process zip file', status=400)