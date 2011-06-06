"""
Module is intended as a helper to prevent cyclic dependencies between models
and to prevent database queries before database tables are created.

It is recommended this code is left alone or can be combined with other module
which is not dependent on any database model nor already existing db connection
for facilitating the normal order of loading modules.
"""

import logging
import traceback

def iterchoices(func):
    """Iterator for lazy evaluating of choices for database models.

    Usage:
        class SomeNewModel(models.Model):
           abc = XyzChoiceCharField('SomeModelName',... choices=iterchoices(get_choices)))
    Function for evaluating items of 'choices' is not evaluated when class SomeNeModel is inicialized.
    It is called by database model only one time when first needed, not earlier than when all odher models are initialised.
    First possible usage is for Django commands internal attribute "requires_model_validation = True",
    by e.g. dbsync, validate and typically commands changing structure of database.
    """
    for item in func():
       yield item


def iterchoices_db(func):
    """Iterator for lazy evaluating of choices for database models, extended for functions which need database access to get results.

    When model is thoroughly validated by database management commands (e.g. dbsync), 
    all call to "func" are skipped to prevent possible database queries before database tables are created.
    (Database connection could be broken without this with some db engines)
    Other is similar to "iterchoices".
    """
    log = logging.getLogger('iterchoices')
    # This test determines, for which Django manage commands should be skipped the call to "func"
    # Skip for all commands which can be useful before dbsync. Call for runserver, runcgi, shell.
    # For other commands is good either call or skip.
    # I hope that this hack will remain functional until I make changes to Livesettings (and maybe enhancement to django.db)
    # and until all users installs them. Then would not be important to skip anything.
    if len(filter(lambda x:
               x[0].find('/core/management/validation.') >= 0 and x[2] == 'get_validation_errors' and x[3].find('choices') >= 0 or
               x[0].find('/core/management/base.') >= 0       and x[2] == 'execute'               and x[3].find('self.validate') >= 0 or
               x[0].find('/core/commands/validate.') >= 0     and x[2] == 'handle_noargs'         and x[3].find('self.validate') >= 0,
               traceback.extract_stack(limit=6))) < 2:
       #
       log.debug('Called model choices initialization function <%s>' % str(func).split()[1])
       for item in func():
           yield item
    else:
       log.info('Skipped model choices initialization function <%s> because of model validation (e.g. syncdb)' % str(func).split()[1])
