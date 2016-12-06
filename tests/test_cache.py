#!/usr/bin/python
# coding: utf8

import unittest
import time
import logging
from flask import Flask
from flask_dogpile import FlaskDogpile


class CacheTest(unittest.TestCase):
    def setUp(self):
        config = {
            "TESTING": True,
            "DEBUG": True,
            "DOGPILE_BACKEND": 'dogpile.cache.redis',
            "DOGPILE_BACKEND_URL": "localhost:3679",
            "DOGPILE_BACKEND_ARGUMENTS": {'distributed_lock': True,
                                          'redis_expiration_time': 5},
            "DOGPILE_REGIONS": [("my_region", 5), ("region2", 5)]
        }
        self.app = Flask(__name__)
        self.app.debug = True
        self.app.config['TESTING'] = True
        self.app.config.update(config)
        self.cache = FlaskDogpile()
        self.cache.init_app(self.app)
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()
        self.app = None
        self.app_context = None

    @classmethod
    def tearDownClass(cls):
        pass

    @classmethod
    def setUpClass(cls):
        logging.basicConfig(level=logging.INFO)

    def test_simple_cached(self):
        @self.cache.my_region.cache_on_arguments()
        def my_function(foo, bar, a="b"):
            my_function.called += 1
            return my_function.called
        my_function.called = 0

        r1 = my_function("a", "hi")
        r2 = my_function("a", "hi")
        r3 = my_function("b", "hi")
        r4 = my_function("b", "hi", "c")
        r5 = my_function("a", "hi", a="b")
        r6 = my_function("a", "hi", "b")

        self.assertEqual(r1, 1)
        self.assertEqual(r2, 1)
        self.assertEqual(r3, 2)
        self.assertEqual(r4, 3)
        self.assertEqual(r5, 1)
        self.assertEqual(r6, 1)

        my_function.invalidate("a", "hi", a="b")
        r1 = my_function("a", "hi")
        self.assertEqual(r1, 4)
        r1 = my_function("a", "hi", a="b")
        self.assertEqual(r1, 4)

        r1 = my_function.refresh("a", "hi", a="b")
        self.assertEqual(r1, 5)

    def test_set(self):
        @self.cache.region2.cache_on_arguments()
        def my_func(foo, bar, a="b"):
            my_func.called += 1
            return my_func.called
        my_func.called = 0

        r1 = my_func("a", "hi")
        r2 = my_func("a", "hi", a="b")
        self.assertEqual(r1, 1)
        self.assertEqual(r2, 1)

        my_func.set(99, "a", "hi", a="b")
        r1 = my_func("a", "hi", a="b")
        self.assertEqual(r1, 99)
        r1 = my_func("a", "hi")
        self.assertEqual(r1, 99)

        my_func.refresh("a", "hi")
        r1 = my_func("a", "hi")
        self.assertEqual(r1, 2)
