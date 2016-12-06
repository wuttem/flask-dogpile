#!/usr/bin/python
# coding: utf8

__version__ = '0.1.0'

from flask import current_app
try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack
from dogpile.cache import make_region
from dogpile.cache.util import kwarg_function_key_generator
from dogpile.cache.util import sha1_mangle_key

class FlaskDogpile(object):
    def __init__(self, app=None):
        self.app = app
        self._regions = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.config.setdefault("DOGPILE_BACKEND", 'dogpile.cache.redis')
        app.config.setdefault("DOGPILE_BACKEND_URL", 'localhost:3679')
        app.config.setdefault("DOGPILE_BACKEND_ARGUMENTS", None)
        app.config.setdefault("DOGPILE_REGIONS", [("default", 3600)])

    def create_regions(self):
        region_config = current_app.config['DOGPILE_REGIONS']
        backend = current_app.config['DOGPILE_BACKEND']
        backend_args = current_app.config['DOGPILE_BACKEND_ARGUMENTS']
        backend_url = current_app.config['DOGPILE_BACKEND_URL']
        regions = {}
        for name, expiration in region_config:
            args = {"url": backend_url}
            args.update(backend_args)
            r = make_region(
                name=name,
                function_key_generator=kwarg_function_key_generator,
                key_mangler=sha1_mangle_key).configure(
                    backend=backend,
                    expiration_time=int(expiration),
                    arguments=args)
            regions[name] = r
        return regions

    @property
    def regions(self):
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'dogpile'):
                ctx.dogpile_regions = self.create_regions()
            return ctx.dogpile_regions
        else:
            raise RuntimeError("No flask context")

    def __getattr__(self, name):
        """
        Override of attribute built-in

        We can access our regions with . syntax:
        cache.myregion
        """
        if name in self.regions:
            return self.regions[name]
        raise AttributeError("Cache region not found")
