"""Статик файллар учун версияли URL ва ихчам JSON."""
import json

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# json_script билан бир хил хавфсиз алмаштиришлар
_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


@register.simple_tag
def asset(path):
    """Файл ўзгарганда URL ҳам ўзгаради — браузер эски нусхани ишлатмайди."""
    url = static(path)
    found = finders.find(path)
    if found:
        import os
        url += f"?v={int(os.path.getmtime(found))}"
    return url


@register.simple_tag
def json_data(value, element_id):
    """Кирилл матнни \\uXXXX га айлантирмасдан, ихчам JSON."""
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).translate(_ESCAPES)
    return format_html('<script id="{}" type="application/json">{}</script>', element_id, mark_safe(data))
