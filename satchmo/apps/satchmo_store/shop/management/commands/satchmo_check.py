from django.core.management.base import NoArgsCommand
from django.core import urlresolvers
from django.utils.importlib import import_module
import logging
import re
import sys
import django
from decimal import Decimal
import types
from distutils.version import LooseVersion

errors = []
log = logging.getLogger('satchmo_check')

class Command(NoArgsCommand):
    help = "Check the system to see if the Satchmo components are installed correctly."
    
    # These settings help to not import some dependencies before they are
    can_import_settings = False
    requires_model_validation = False

    def handle_noargs(self, **options):
        """Checks Satchmo installation and configuration.

        Tests, catches and shortly summarizes many common installation errors, without tracebacks.
        If was seen a traceback, it should be reported to a developer. (for now)
        Tracebacks are saved to the 'satchmo.log'. It helps to find cyclic dependencies etc.
        """
        #    print_out(...)  # print immediately and log it
        #    error_out(...)  # print at the end and log it now
        from django.conf import settings
        print_out("Checking your satchmo configuration.")
        try:
            import satchmo_store
        except ImportError:
            error_out("Satchmo is not installed correctly. Please verify satchmo is on your sys path.")
        print_out("Using Django version %s" % django.get_version())
        print_out("Using Satchmo version %s" % satchmo_store.get_version())
        #Check the Django version
        #Make sure we only get the X.Y.Z version info and not any other alpha or beta designations
        version_check = LooseVersion(".".join(map(str, django.VERSION)[:3]))
        if version_check < LooseVersion("1.2.3"):
            error_out("Django version must be >= 1.2.3")

        # Try importing all our dependencies
        verbose_check_install('', 'Crypto.Cipher', verbose_name='The Python Cryptography Toolkit')
        try:
            import Image
            verbose_check_install('Image', 'Image')
        except ImportError:
            verbose_check_install('PIL', 'PIL', verbose_name='The Python Imaging Library')

        verbose_check_install('reportlab', 'reportlab', '2.3')

        verbose_check_install('TRML2PDF', 'trml2pdf', '1.0', verbose_name='Tiny RML2PDF')

        verbose_check_install('django_registration', 'registration', '0.7')

        verbose_check_install('', 'yaml', verbose_name='YAML')

        verbose_check_install('sorl_thumbnail', 'sorl', '3.2.5', 'caf69b520632', 'Sorl imaging library')

        verbose_check_install('django_caching_app_plugins', 'app_plugins', '0.1.2', '53a31761e344')

        verbose_check_install('django_livesettings', 'livesettings', '1.4.8', 'e2769f9f60ec')

        verbose_check_install('django_signals_ahoy', 'signals_ahoy', '0.1.0', '9ad8779d4c63')

        verbose_check_install('django_threaded_multihost', 'threaded_multihost', '1.4.1', '7ca3743d8a70')

        verbose_check_install('django-keyedcache', 'keyedcache', '1.4.4', '4be18235b372')

        try:
            cache_avail = settings.CACHE_BACKEND
        except AttributeError:
            error_out("A CACHE_BACKEND must be configured.")
        # Try looking up a url to see if there's a misconfiguration there    
        try:
            url = urlresolvers.reverse('satchmo_search')
            # Catch SystemExit, because if an error occurs, `urlresolvers` usually calls sys.exit() and other error messages would be lost.
        except (Exception, SystemExit), e:
            error_out("Unable to resolve url. Received error - %s" % e)
        from l10n.l10n_settings import get_l10n_default_currency_symbol
        if not isinstance(get_l10n_default_currency_symbol(),types.UnicodeType):
            error_out("Your currency symbol should be a unicode string.")
        if 'satchmo_store.shop.SSLMiddleware.SSLRedirect' not in settings.MIDDLEWARE_CLASSES:
            error_out("You must have satchmo_store.shop.SSLMiddleware.SSLRedirect in your MIDDLEWARE_CLASSES.")
        if 'satchmo_store.shop.context_processors.settings' not in settings.TEMPLATE_CONTEXT_PROCESSORS:
            error_out("You must have satchmo_store.shop.context_processors.settings in your TEMPLATE_CONTEXT_PROCESSORS.")
        if 'threaded_multihost.middleware.ThreadLocalMiddleware' not in settings.MIDDLEWARE_CLASSES:
            error_out("You must install django threaded multihost \n and place threaded_multihost.middleware.ThreadLocalMiddleware in your MIDDLEWARE_CLASSES.")
        if 'satchmo_store.accounts.email-auth.EmailBackend' not in settings.AUTHENTICATION_BACKENDS:
            error_out("You must have satchmo_store.accounts.email-auth.EmailBackend in your AUTHENTICATION_BACKENDS")
        if len(settings.SECRET_KEY) == 0:
            error_out("You must have SECRET_KEY set to a valid string in your settings.py file")
        python_ver = Decimal("%s.%s" % (sys.version_info[0], sys.version_info[1]))
        if python_ver < Decimal("2.4"):
            error_out("Python version must be at least 2.4.")
        if python_ver < Decimal("2.5"):
            try:
                from elementtree.ElementTree import Element
            except ImportError:
                error_out("Elementtree is not installed.")

        # Check all installed apps
        if not filter(lambda x: re.search('not .*(installed|imported)', x), errors):
            for appname in settings.INSTALLED_APPS:
                try:
                    app = import_module(appname)
                except (Exception, SystemExit):
                    error_out('Can not import "%s"' % appname) 
                    log.exception('Can not import "%s"' % appname)
        else:
            log.debug('It does not test INSTALLED_APPS due to previous errors.')

        if len(errors) == 0:
            print_out("Your configuration has no errors.")
        else:
            print_out(""); print_out("The following errors were found:")
            for error in errors:
                print_out(error)
            if filter(lambda x: re.search('not .*import(ed)?', x), errors):
                print "Error details are in 'satchmo.log'"

def print_out(msg):
    log.info(msg)
    print msg

def error_out(msg):
    log.error(msg)
    errors.append(msg)

APP_NOT_FOUND, APP_OLD_VERSION, APP_IMPORT_FAIL, APP_OK = range(4)

def check_install(project_name, appname, min_version=None, hg_hash=None):
    """Checks if package is installed, version is greater or equal to the required and can be imported.
    
    This uses different methods of determining the version for diffenent types of installation
    in this order: app.get_version() (custom), app.VERSION (tuple), app.__version__ (string), mercurial hash, setuptools version

      project_name  # verbose name for setuptools (can be with "-")
      package_name  # package name for python import
      min_version   # minimal required version (>=min_version)
      hg_hash       # hg hash of the commit, which should be in the repository. This should be consistent to min_version.
                      (A developper need not eventually to use specified important version (need not hg up tip) but should be informed to do pull.)
                      One met condition is sufficient.

    Returns tuple:  (result_code,     # any of APP_* constants
                     version_string)
    The import problem can be caused by a dependency on other packages and therefore it is differentiated from not installed.
    """
    # Version number can be obtained even without any requirements for a version this way: (all versions meet this)
    #    check_install(project_name, appname, min_version='.', hg_hash='')
    import imp
    import os
    import time
    isfound = isimported = False
    pkgtype = isversion = None
    version = ''
    try:
        # find it only
        lpos = 0
        path = None
        while lpos < len(appname):
            rpos = (appname.find('.', lpos) < 0) and len(appname) or appname.find('.', lpos)
            dummyfile, filename, (suffix, mode, pkgtype) = imp.find_module(appname[lpos:rpos], path)
            path = [filename]
            lpos = rpos + 1
        isfound = True
        try:
            # import it
            app = __import__(appname)
            isimported = True
        except ImportError:
            log.exception('Can not import "%s"' % appname)
    except ImportError:
        pass

    if isimported:
        try:
            # get version from app
            if hasattr(app, 'get_version'):
                get_version = app.get_version
                if callable(get_version):
                    version = get_version()
                else:
                    version = get_version
            elif hasattr(app, 'VERSION'):
                version = app.VERSION
            elif hasattr(app, '__version__'):
                version = app.__version__
            if isinstance(version, (list, tuple)):
                version = '.'.join(map(str, version))
            if version and version[0].isdigit() and min_version:
                isversion = LooseVersion(version) >= LooseVersion(min_version)
        except:
            pass

    if pkgtype == imp.PKG_DIRECTORY:   # and hg_hash != None and (version == None or not version[0].isdigit()):
        try:
            # get version from mercurial
            from mercurial import ui, hg
            try:
                linkpath = os.readlink(filename)
                dirname = os.path.join(os.path.dirname(filename), linkpath)
            except:
                dirname = filename
            repo = None
            hg_dir = os.path.normpath(os.path.join(dirname, '..'))
            repo = hg.repository(ui.ui(), hg_dir)
            try:
                node_id = repo.changelog.lookup(hg_hash)
                isversion = True
                #node = repo[node_id]    # required node
                node = repo['.']        # current node
                datestr = time.strftime('%Y-%m-%d', time.gmtime(node.date()[0]))
                version_hg = "hg-%s:%s %s" % (node.rev(), node.hex()[0:12], datestr)
                version = (version + ' ' + version_hg).strip()
            except:
                isversion = isversion or False
        except:
            pass

    if isfound and min_version and project_name and isversion == None:
        try:
            # get version from setuptools
            from pkg_resources import require
            version = require(project_name)[0].version
            isversion = isversion or False
            require('%s >=%s' % (project_name, min_version))
            isversion = True
        except:
            pass
    # If no required version specified, then it is also OK
    isversion = isversion or (isversion == None and min_version == None)
    result = isfound and (isversion and (isimported and APP_OK or APP_IMPORT_FAIL) or APP_OLD_VERSION) or APP_NOT_FOUND
    return (result, version)

def verbose_check_install(project_name, appname, min_version=None, hg_hash=None, verbose_name=None):
    result, version = check_install(project_name, appname, min_version, hg_hash)
    verbose_name = (verbose_name or re.sub('[_-]', ' ', appname.capitalize()))
    log.debug('%s: found version %s ' % (verbose_name, version or '(unknown)'))
    if result == APP_NOT_FOUND:
        msg = 'is not installed.'
    elif result == APP_OLD_VERSION:
        msg = 'should be upgraded to version %s or newer.' % min_version
    elif result == APP_IMPORT_FAIL:
        msg = 'can not be imported now, but the right version is probably installed. Maybe dependency problem.'
    elif result == APP_OK:
        msg = None
    if msg:
        error_out(' '.join((verbose_name, msg)))
