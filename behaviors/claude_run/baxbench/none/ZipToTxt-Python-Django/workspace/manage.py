#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Default to running on 0.0.0.0:5000
    args = sys.argv
    if len(args) >= 2 and args[1] == 'runserver' and len(args) == 2:
        args = args + ['0.0.0.0:5000']

    execute_from_command_line(args)


if __name__ == '__main__':
    main()