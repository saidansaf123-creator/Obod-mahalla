"""Excel манзилли дастурни базага юклаш.

    python manage.py import_excel            # охирги юкланган файл (базада) ёки data/Обод_махалла_2027.xlsx
    python manage.py import_excel --file X   # аниқ файлдан
Ижро журнали (амалда) сақланади ва янги ишларга қайта боғланади.
"""
import os

from django.core.management.base import BaseCommand

from apps.energy import services
from apps.energy.source import read


class Command(BaseCommand):
    help = "«Обод маҳалла 2027» манзилли дастури файлини базага юклайди"

    def add_arguments(self, parser):
        parser.add_argument("--file", help="Excel файл йўли")
        parser.add_argument("--no-excel", action="store_true", help="(эски буйруқлар билан мослик учун)")

    def handle(self, *args, file=None, **opts):
        if file:
            path, name, tmp = file, os.path.basename(file), False
        else:
            path, name, tmp = services.current_source()
        try:
            src = read(path)
        finally:
            if tmp:
                os.remove(path)
        src.path = type(src.path)(name)
        res = services.load(src)
        services.bump_version()
        self.stdout.write(self.style.SUCCESS(
            f"{name}: {res['districts']} туман, {res['mahallas']} маҳалла, {res['works']} иш, "
            f"{res['sections']} ТП секцияси; журнал: {res['entries_linked']} боғланди, {res['entries_orphan']} боғланмади."))
