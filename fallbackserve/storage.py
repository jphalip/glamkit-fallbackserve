import os
import urllib
import urllib2

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.utils.encoding import smart_str


class FallbackStorage(FileSystemStorage):
    def __init__(self, option=None):
        self._fetching = False
        return super(FallbackStorage, self).__init__(option)


    def _open(self, name, mode='rb'):
        try:
            return super(FallbackStorage, self)._open(name, mode)
        except IOError, e:
            if e.errno == 2:
                try:
                    self.fetch_remote(name)
                    # try again..
                    return super(FallbackStorage, self)._open(name, mode)
                except Exception, e2:
                    raise e # raise outer error and pretend we didn't try this step
            else:
                raise


    def path(self, name):
        """you want my path, sure but i'll fetch it if it doesn't exist"""
        p = super(FallbackStorage, self).path(name)
        if not self._fetching and not os.path.exists(p):
            try:
                self.fetch_remote(name)
            except Exception, e:
                pass # ignore
        return p


    def fetch_remote(self, name):
        self._fetching = True
        fallback_server = settings.FALLBACK_STATIC_URL
        auth_user = getattr(settings, 'FALLBACK_STATIC_URL_USER', None)
        auth_pass = getattr(settings, 'FALLBACK_STATIC_URL_PASS', None)
        if name.startswith(settings.MEDIA_ROOT):
            name = name[len(settings.MEDIA_ROOT):].lstrip('/')
        if settings.MEDIA_URL.startswith('http://'):
            media_server = settings.MEDIA_URL.rstrip('/')
        else:
            media_server = fallback_server.rstrip('/')
        # Convert the filename into bytes (if it's Unicode) and escape chars
        fq_url = '%s/%s' % (media_server, urllib.quote(smart_str(name)))
        print "FallbackStorage: trying to fetch from %s" % fq_url
        try:
            handlers = []
            if auth_user or auth_pass:
                passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
                passman.add_password(None, fallback_server, auth_user, auth_pass)
                authhandler = urllib2.HTTPBasicAuthHandler(passman)
                handlers.append(authhandler)
            opener = urllib2.build_opener(*handlers)
            contents = opener.open(fq_url).read()
        except urllib2.HTTPError, e:
            self._fetching = False
            raise e
        else:
            # save it
            self._save(name, ContentFile(contents))
        self._fetching = False
