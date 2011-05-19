from django import template

register = template.Library()

def product_upsell(context, product):
    """
    Display the list of products that are upsell candidates for currently viewed product.
    """
    goals = None
    if product.upselltargets.count() > 0:
        goals = product.upselltargets.all()

    return template.RequestContext(context['request'], { 'goals' : goals })
register.inclusion_tag("upsell/product_upsell.html", takes_context=True)(product_upsell)
