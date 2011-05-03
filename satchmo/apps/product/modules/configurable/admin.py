from django.contrib import admin
from product.modules.configurable.models import ConfigurableProduct, ProductVariation

class ProductVariationOptions(admin.ModelAdmin):
    '''
    Makes the fields product and parent read-only.

    Letting the user change the parent on an existing ProductVariation
    will just confuse things, and probably never makes sense.

    If the product_id has been assigned externally (usually by a link
    from said product), then we want it to not be user changeable so it
    doesn't get changed by mistake.
    '''
    readonly_fields = ['product', 'parent',]
    fields = ['product', 'parent', 'options',]
    filter_horizontal = ('options',)

class ConfigurableProductAdmin(admin.ModelAdmin):
    '''
    Makes the field product read-only.

    If the product_id has been assigned externally (usually by a link
    from said product), then we want it to not be user changeable so it
    doesn't get changed by mistake.
    '''
    readonly_fields = ['product',]
    fields = ['product', 'create_subs', 'option_group',]

admin.site.register(ConfigurableProduct, ConfigurableProductAdmin)
admin.site.register(ProductVariation, ProductVariationOptions)


