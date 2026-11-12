from django import template

register = template.Library()


@register.filter
def fmt(v):
    if v is None or v == "":
        return "-"
    try:
        return f"{int(v):,}".replace(",", " ")
    except (ValueError, TypeError):
        return v


@register.filter
def kun(d):
    return d.strftime("%d.%m.%Y") if d else ""


@register.filter
def sana_vaqt(d):
    return d.strftime("%d.%m.%Y %H:%M") if d else ""
