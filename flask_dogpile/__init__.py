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
from functools import wraps

class FlaskDogpile(object):
    FUNC_REGION_NAME_ATTR = 'dogpile_cache_region_name'

    def __init__(self, app=None):
        self.app = app
        self._regions = None
        self._regions_decorators = None
        self._regions_decorators_multi = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.config.setdefault("DOGPILE_BACKEND", 'dogpile.cache.redis')
        app.config.setdefault("DOGPILE_BACKEND_URL", 'localhost:3679')
        app.config.setdefault("DOGPILE_BACKEND_ARGUMENTS", None)
        app.config.setdefault("DOGPILE_REGIONS", [("default", 3600)])
        self.create_regions(app)
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['dogpile_cache'] = self

    def create_regions(self, app):
        region_config = app.config['DOGPILE_REGIONS']
        backend = app.config['DOGPILE_BACKEND']
        backend_args = app.config['DOGPILE_BACKEND_ARGUMENTS']
        backend_url = app.config['DOGPILE_BACKEND_URL']
        self._regions = {}
        self._regions_decorators = {}
        self._regions_decorators_multi = {}
        for name, expiration in region_config:
            args = {"url": backend_url}
            if backend_args is not None:
                args.update(backend_args)
            r = make_region(
                name=name,
                function_key_generator=kwarg_function_key_generator,
                key_mangler=sha1_mangle_key).configure(
                    backend=backend,
                    expiration_time=int(expiration),
                    arguments=args)
            self._regions[name] = r
            self._regions_decorators[name] = r.cache_on_arguments()
            self._regions_decorators_multi[name] = r.cache_multi_on_arguments()
        return self._regions

    @property
    def regions(self):
        if self._regions is None:
            raise RuntimeError("No flask context")
        return self._regions

    def cache_on_region(self, name):
        def decorator(func):
            setattr(func, self.FUNC_REGION_NAME_ATTR, name)
            setattr(func, "multi", False)
            @wraps(func)
            def wrapper(*args):
                if name in self._regions:
                    cache_decorator = self.get_region_decorator(name)
                    return cache_decorator(func)(*args)
                else:
                    raise KeyError("You didn't specified region `%s`" % name)
            return wrapper
        return decorator

    def cache_on_region_multi(self, name):
        def decorator(func):
            setattr(func, self.FUNC_REGION_NAME_ATTR, name)
            setattr(func, "multi", True)
            @wraps(func)
            def wrapper(*args):
                if name in self._regions:
                    cache_decorator = self.get_region_decorator_multi(name)
                    return cache_decorator(func)(*args)
                else:
                    raise KeyError("You didn't specified region `%s`" % name)
            return wrapper
        return decorator

    def get_region(self, region_name):
        if self._regions is None:
            raise RuntimeError("No flask context")
        return self._regions[region_name]

    def get_region_decorator(self, region_name):
        if self._regions_decorators is None:
            raise RuntimeError("No flask context")
        return self._regions_decorators[region_name]

    def get_region_decorator_multi(self, region_name):
        if self._regions_decorators_multi is None:
            raise RuntimeError("No flask context")
        return self._regions_decorators_multi[region_name]

    def invalidate_region(self, region_name, hard=True):
        region = self.get_region(region_name)
        region.invalidate(hard)

    def invalidate_all_regions(self, hard=True):
        for region_name in self.regions.keys():
            self.invalidate_region(region_name, hard)

    def invalidate(self, func, *args):
        region_name = getattr(func, self.FUNC_REGION_NAME_ATTR)
        if getattr(func, "multi"):
            decorator = self.get_region_decorator_multi(region_name)
        else:
            decorator = self.get_region_decorator(region_name)
        func = decorator(func)
        return func.invalidate(*args)

    def refresh(self, func, *args):
        region_name = getattr(func, self.FUNC_REGION_NAME_ATTR)
        if getattr(func, "multi"):
            decorator = self.get_region_decorator_multi(region_name)
        else:
            decorator = self.get_region_decorator(region_name)
        func = decorator(func)
        return func.refresh(*args)

    def set(self, func, value, *args):
        region_name = getattr(func, self.FUNC_REGION_NAME_ATTR)
        if getattr(func, "multi"):
            decorator = self.get_region_decorator_multi(region_name)
        else:
            decorator = self.get_region_decorator(region_name)
        func = decorator(func)
        return func.set(value, *args)
