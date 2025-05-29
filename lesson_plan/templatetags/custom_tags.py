from django import template
import markdown

register = template.Library()


@register.filter
def get_item(obj, key):
    return getattr(obj, key, "")


@register.filter
def markdownify(value):
    return markdown.markdown(value)


@register.filter
def attr(obj, attr_name):
    return getattr(obj, attr_name, "")
