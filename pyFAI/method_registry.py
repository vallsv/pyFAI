#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#    Project: Fast Azimuthal integration
#             https://github.com/silx-kit/pyFAI
#
#    Copyright (C) 2014-2018 European Synchrotron Radiation Facility, Grenoble, France
#
#    Principal author:       Jérôme Kieffer (Jerome.Kieffer@ESRF.eu)
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#  .
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#  .
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#  THE SOFTWARE.

"""
Contains a registry of all integrator available 
"""

__author__ = "Jerome Kieffer"
__contact__ = "Jerome.Kieffer@ESRF.eu"
__license__ = "MIT"
__copyright__ = "European Synchrotron Radiation Facility, Grenoble, France"
__date__ = "05/12/2018"
__status__ = "development"

from collections import OrderedDict, namedtuple
Method = namedtuple("Method", ["dim", "split", "algo", "impl", "target"])


class IntegrationMethod:
    "Keeps track of all integration methods"
    _registry = OrderedDict()

    @classmethod
    def list_available(cls):
        """return a list of pretty printed integration method available"""
        return [i.__repr__() for i in cls._registry.values()]

    @classmethod
    def select_method(cls, dim, split=None, algo=None, impl=None, method_nt=None):
        """Retrieve all algorithm which are fitting the requirement
        """
        if method_nt is not None:
            dim, algo, split, split = method_nt[:4]
        dim = int(dim)
        algo = algo.lower() if algo is not None else "*"
        impl = impl.lower() if impl is not None else "*"
        split = split.lower() if split is not None else "*"
        method_nt = Method(dim, algo, impl, split, None)
        if method_nt in cls._registry:
            return [cls._registry[method_nt]]
        # Validate on pixel splitting, implementation and algorithm

        candidates = [i for i in cls._registry.keys() if i[0] == dim]
        if split != "*":
            candidates = [i for i in candidates if i[3] == split]
        if algo != "*":
            candidates = [i for i in candidates if i[1] == algo]
        if impl != "*":
            candidates = [i for i in candidates if i[2] == impl]
        return [cls._registry[i] for i in candidates]

    @classmethod
    def select_old_method(cls, dim, old_method):
        """Retrieve all algorithm which are fitting the requirement from old_method
        valid 
        "numpy", "cython", "bbox" or "splitpixel", "lut", "csr", "nosplit_csr", "full_csr", "lut_ocl" and "csr_ocl"
        """
        results = []
        for v in cls._registry.values():
            if (v.dimension == dim) and (v.old_method_name == old_method):
                results.append(v)
        if results:
            return results
        dim = int(dim)
        algo = "*"
        impl = "*"
        split = "*"
        old_method = old_method.lower()
        if "lut" in old_method:
            algo = "lut"
        elif "csr" in old_method:
            algo = "csr"

        if "ocl" in old_method:
            impl = "opencl"

        if "bbox" in old_method:
            split = "bbox"
        elif "full" in old_method:
            split = "full"
        elif "no" in old_method:
            split = "no"
        return cls.select_method(dim, split, algo, impl)

    @classmethod
    def is_available(cls, dim, split=None, algo=None, impl=None, method_nt=None):
        """
        Check if the method is currently available
        
        :param dim: 1 or 2D integration
        :param split: pixel splitting options "no", "BBox", "pseudo", "full"
        :param algo: "histogram" for direct integration, LUT or CSR for sparse
        :param impl: "python", "cython" or "opencl" to describe the implementation
        :param method_nt: a Method namedtuple with (split, algo, impl)
        :return: True if such integrator exists
        """
        if method_nt is None:
            algo = algo.lower() if algo is not None else ""
            impl = impl.lower() if impl is not None else ""
            split = split.lower() if split is not None else ""
            method_nt = Method(algo, impl, split)
        return method_nt in cls._registry

    @classmethod
    def parse(cls, smth, dim=1):
        """Parse the string for the content
         
        """
        res = []
        if isinstance(smth, cls):
            return smth
        if isinstance(smth, Method) and cls.is_available(method_nt=smth):
            return cls._registry[smth]
        if isinstance(smth, str):
            comacount = smth.count(",")
            if comacount <= 1:
                res = cls.select_old_method(dim, smth)
            else:
                res = cls.select_method(dim, smth)
        if res:
            return res[0]

    def __init__(self, dim, split, algo, impl, target=None, target_name=None,
                 class_=None, function=None, old_method=None, extra=None):
        """Constructor of the class, only registers the 
        :param dim: 1 or 2 integration engine
        :param split: pixel splitting options "no", "BBox", "pseudo", "full"
        :param algo: "histogram" for direct integration, LUT or CSR for sparse
        :param impl: "python", "cython" or "opencl" to describe the implementation
        :param target: the OpenCL device as 2-tuple of indices
        :param target_name: Full name of the OpenCL device
        :param class_: class used to instanciate
        :param function: function to be called
        :param old_method: former method name (legacy)
        :param extra: extra informations
        """
        self.dimension = dim
        self.algorithm = algo
        self.pixel_splitting = split
        self.implementation = impl
        self.target = target
        self.target_name = target_name or str(target)
        self.class_ = class_
        self.function = function
        self.old_method_name = old_method
        self.extra = extra
        self.method = Method(dim, algo.lower(), impl.lower(), split.lower(), target)
        self.__class__._registry[self.method] = self

    def __repr__(self):
        if self.target:
            return ", ".join((str(self.dimension) + "d int", self.pixel_splitting + " split", self.algorithm, self.implementation, self.target_name))
        else:
            return ", ".join((str(self.dimension) + "d int", self.pixel_splitting + " split", self.algorithm, self.implementation))
