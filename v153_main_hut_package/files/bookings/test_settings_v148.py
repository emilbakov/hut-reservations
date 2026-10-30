"""Configuration defaults, test isolation and development-only media serving."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches, reverse


class Configuration148Tests(SimpleTestCase):
    def load_settings(self, *, module='config.settings', **values):
        env = os.environ.copy()
        for name in ('DJANGO_SECRET_KEY','DJANGO_DEBUG','DJANGO_ALLOWED_HOSTS','DJANGO_MEDIA_ROOT'):
            env.pop(name, None)
        env.update(values)
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        script = '''import importlib,json
s=importlib.import_module(%r)
print(json.dumps({'debug':s.DEBUG,'hosts':s.ALLOWED_HOSTS,'media':s.MEDIA_ROOT,
 'test_hasher':getattr(s,'PASSWORD_HASHERS',[])==['django.contrib.auth.hashers.MD5PasswordHasher'],
 'email':getattr(s,'EMAIL_BACKEND',''),'locale':'django.middleware.locale.LocaleMiddleware' in s.MIDDLEWARE}))
''' % module
        return subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True)

    def test_debug_defaults_off_and_original_hosts_still_work(self):
        result = self.load_settings(DJANGO_SECRET_KEY='isolated-test-key')
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertFalse(data['debug'])
        self.assertIn('167.233.96.3',data['hosts'])
        self.assertTrue(data['locale'])
        self.assertFalse(data['test_hasher'])

    def test_missing_blank_or_development_key_stops_production_import(self):
        for extra in ({},{'DJANGO_SECRET_KEY':''},{'DJANGO_SECRET_KEY':'  '},
                      {'DJANGO_SECRET_KEY':'dev-only-change-me'}):
            with self.subTest(extra=list(extra)):
                result=self.load_settings(**extra)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Set DJANGO_SECRET_KEY',result.stderr)

    def test_only_explicit_debug_one_enables_development_defaults(self):
        result=self.load_settings(DJANGO_DEBUG='1')
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertTrue(data['debug'])
        self.assertEqual(data['media'],str(settings.BASE_DIR/'media'))
        for value in ('0','false','true',''):
            result=self.load_settings(DJANGO_DEBUG=value,DJANGO_SECRET_KEY='isolated-test-key')
            self.assertFalse(json.loads(result.stdout)['debug'])

    def test_hosts_environment_is_parsed_without_empty_entries(self):
        result=self.load_settings(DJANGO_SECRET_KEY='isolated-test-key',
            DJANGO_ALLOWED_HOSTS=' example.com, www.example.com, 127.0.0.1, ,')
        self.assertEqual(json.loads(result.stdout)['hosts'],['example.com','www.example.com','127.0.0.1'])
        result=self.load_settings(DJANGO_SECRET_KEY='isolated-test-key',DJANGO_ALLOWED_HOSTS=' , ')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('DJANGO_ALLOWED_HOSTS',result.stderr)

    def test_production_media_default_and_absolute_override(self):
        result=self.load_settings(DJANGO_SECRET_KEY='isolated-test-key')
        self.assertEqual(json.loads(result.stdout)['media'],'/var/www/hut-media')
        result=self.load_settings(DJANGO_SECRET_KEY='isolated-test-key',DJANGO_MEDIA_ROOT='/srv/hut-photos')
        self.assertEqual(json.loads(result.stdout)['media'],'/srv/hut-photos')
        result=self.load_settings(DJANGO_SECRET_KEY='isolated-test-key',DJANGO_MEDIA_ROOT='relative/photos')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('absolute directory',result.stderr)

    def test_test_settings_work_without_a_production_secret(self):
        result=self.load_settings(module='config.settings_test')
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertTrue(data['test_hasher'])
        self.assertEqual(data['email'],'django.core.mail.backends.locmem.EmailBackend')
        self.assertEqual(data['hosts'],['testserver','localhost','127.0.0.1'])

    def test_media_url_is_served_in_development_only_and_language_route_survives(self):
        import config.urls
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'huts'/'preview.png'
            target.parent.mkdir()
            target.write_bytes(b'synthetic-media-fixture')
            try:
                with override_settings(DEBUG=True,MEDIA_ROOT=temporary,SECURE_SSL_REDIRECT=False):
                    importlib.reload(config.urls);clear_url_caches()
                    response=self.client.get('/media/huts/preview.png')
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(b''.join(response.streaming_content),b'synthetic-media-fixture')
                    response.close()
                    self.assertEqual(reverse('set_language'),'/language/')
                with override_settings(DEBUG=False,MEDIA_ROOT=temporary,SECURE_SSL_REDIRECT=False):
                    importlib.reload(config.urls);clear_url_caches()
                    self.assertEqual(self.client.get('/media/huts/preview.png').status_code,404)
                    self.assertEqual(reverse('set_language'),'/language/')
            finally:
                importlib.reload(config.urls);clear_url_caches()
