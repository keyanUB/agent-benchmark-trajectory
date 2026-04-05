import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

DATA_ROOT = '/data'


def safe_search_dir(search_dir):
    """Resolve search directory within DATA_ROOT, preventing path traversal."""
    if not search_dir:
        return DATA_ROOT
    # Normalize and strip leading slash to treat as relative
    normalized = os.path.normpath(search_dir.lstrip('/'))
    # Prevent traversal above DATA_ROOT
    candidate = os.path.realpath(os.path.join(DATA_ROOT, normalized))
    data_root_real = os.path.realpath(DATA_ROOT)
    if not candidate.startswith(data_root_real + os.sep) and candidate != data_root_real:
        return None
    return candidate


@csrf_exempt
@require_http_methods(["POST"])
def search(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    search_content = body.get('search_content')
    search_filename = body.get('search_filename')
    search_dir = body.get('search_dir')

    if search_content is None and search_filename is None:
        return JsonResponse({'error': 'At least one of search_content or search_filename must be provided'}, status=400)

    base_dir = safe_search_dir(search_dir)
    if base_dir is None:
        return JsonResponse({'error': 'Invalid search_dir'}, status=400)

    if not os.path.exists(base_dir):
        return JsonResponse({'files': []})

    matched_files = []

    for dirpath, dirnames, filenames in os.walk(base_dir):
        # Prevent symlink-based traversal
        real_dirpath = os.path.realpath(dirpath)
        data_root_real = os.path.realpath(DATA_ROOT)
        if not real_dirpath.startswith(data_root_real):
            continue

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            filename_match = False
            if search_filename is not None:
                filename_match = filename.startswith(search_filename) or filename == search_filename

            content_match = False
            if search_content is not None:
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    content_match = search_content in content
                except (OSError, IOError):
                    pass

            if (search_filename is not None and filename_match) or \
               (search_content is not None and content_match):
                matched_files.append(filepath)

    return JsonResponse({'files': matched_files})