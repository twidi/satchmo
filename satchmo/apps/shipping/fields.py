from livesettings import config_choice_values, SettingNotSet

def shipping_choices():
    try:
        return config_choice_values('SHIPPING','MODULES')
    except SettingNotSet:
        return ()
