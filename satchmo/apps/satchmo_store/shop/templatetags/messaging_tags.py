# Have been used only by django-keyedcache 1.4.4 and older.
# Replaced by django.contrib.messages.middleware.MessageMiddleware.
# Could be removed after Django 1.5 is released.

from django import template

register = template.Library()

def show_messages(context):
    from django.contrib import messages
    messages = messages.get_messages(context['request'])
    return {'visitor_messages' : messages }

register.inclusion_tag('shop/_messages.html', takes_context=True)(show_messages)
