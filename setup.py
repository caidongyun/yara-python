#
# Copyright (c) 2007-2013. The YARA Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from distutils.command.build import build
from setuptools import setup, Extension
from codecs import open

import distutils.errors
import distutils.ccompiler
import distutils.sysconfig

import contextlib
import os
import sys
import tempfile
import shutil
import subprocess

@contextlib.contextmanager
def muted(*streams):
  """A context manager to redirect stdout and/or stderr to /dev/null.

  Examples:
    with muted(sys.stdout):
      ...

    with muted(sys.stderr):
      ...

    with muted(sys.stdout, sys.stderr):
      ...
  """
  devnull = open(os.devnull, 'w')
  try:
    old_streams = [os.dup(s.fileno()) for s in streams]
    for s in streams:
      os.dup2(devnull.fileno(), s.fileno())
    yield
  finally:
    for o,n in zip(old_streams, streams):
      os.dup2(o, n.fileno())
    devnull.close()


def has_function(function_name, libraries=None):
  """Checks if a given functions exists in the current platform."""
  compiler = distutils.ccompiler.new_compiler()
  with muted(sys.stdout, sys.stderr):
    result = compiler.has_function(
        function_name, libraries=libraries)
  if os.path.exists('a.out'):
    os.remove('a.out')
  return result


class BuildCommand(build):

  user_options = build.user_options + [
      ('dynamic-linking', None,'link dynamically against libyara'),
      ('enable-cuckoo', None,'enable "cuckoo" module'),
      ('enable-magic', None,'enable "magic" module'),
      ('enable-profiling', None,'enable profiling features')]

  boolean_options = build.boolean_options + [
      'dynamic', 'enable-cuckoo', 'enable-magic', 'enable-profiling']

  def initialize_options(self):
    build.initialize_options(self)
    self.dynamic_linking = None
    self.enable_magic = None
    self.enable_cuckoo = None
    self.enable_profiling = None

  def finalize_options(self):
    build.finalize_options(self)
    if self.enable_magic and self.dynamic_linking:
      raise distutils.errors.DistutilsOptionError(
          '--enable-magic can''t be used with --dynamic-linking')
    if self.enable_cuckoo and self.dynamic_linking:
      raise distutils.errors.DistutilsOptionError(
          '--enable-cuckoo can''t be used with --dynamic-linking')

  def run(self):
    """Execute the build command."""

    base_dir = os.path.dirname(__file__)

    if base_dir:
      os.chdir(base_dir)

    sources = ['yara-python.c']
    exclusions = ['yara/libyara/modules/pe_utils.c']
    libraries = ['yara']
    include_dirs = []
    library_dirs = []
    compile_args = []
    macros = []

    if self.plat_name in ('win32','win-amd64'):
      building_for_windows = True
      bits = '64' if self.plat_name == 'win-amd64' else '32'
      macros.append(('_CRT_SECURE_NO_WARNINGS','1'))
      libraries.append('advapi32')
      libraries.append('user32')
    else:
      building_for_windows = False

    if 'macosx' in self.plat_name:
      building_for_osx = True
      include_dirs.append('/opt/local/include')
      library_dirs.append('/opt/local/lib')
    else:
      building_for_osx = False

    if has_function('memmem'):
      macros.append(('HAVE_MEMMEM', '1'))
    if has_function('strlcpy'):
      macros.append(('HAVE_STRLCPY', '1'))
    if has_function('strlcat'):
      macros.append(('HAVE_STRLCAT', '1'))

    if self.enable_profiling:
      macros.append(('PROFILING_ENABLED', '1'))

    if not self.dynamic_linking:
      libraries.remove('yara')
      include_dirs.extend(['yara/libyara/include', 'yara/libyara/', '.'])

      if building_for_windows:
        include_dirs.append('yara/windows/include')
        library_dirs.append('yara/windows/lib')

      if building_for_windows:
        macros.append(('HASH', '1'))
        libraries.append('libeay%s' % bits)
      elif (has_function('MD5_Init', libraries=['crypto']) and
          has_function('SHA256_Init', libraries=['crypto'])):
        macros.append(('HASH', '1'))
        libraries.append('crypto')
      else:
        exclusions.append('yara/libyara/modules/hash.c')

      if self.enable_magic:
        macros.append(('MAGIC', '1'))
      else:
        exclusions.append('yara/libyara/modules/magic.c')

      if self.enable_cuckoo:
        macros.append(('CUCKOO', '1'))
        if building_for_windows:
          libraries.append('jansson%s' % bits)
        else:
          libraries.append('jansson')
      else:
        exclusions.append('yara/libyara/modules/cuckoo.c')

      exclusions = [os.path.normpath(x) for x in exclusions]

      for directory, _, files in os.walk('yara/libyara/'):
        for x in files:
          x = os.path.normpath(os.path.join(directory, x))
          if x.endswith('.c') and x not in exclusions:
            sources.append(x)

    self.distribution.ext_modules = [Extension(
        name='yara',
        sources=sources,
        include_dirs=include_dirs,
        library_dirs=library_dirs,
        libraries=libraries,
        define_macros=macros,
        extra_compile_args=compile_args)]

    build.run(self)


with open('README.rst', 'r', 'utf-8') as f:
  readme = f.read()

setup(
    name='yara-python',
    version='3.4.0.0',
    description='Python interface for YARA',
    long_description=readme,
    license='Apache 2.0',
    author='Victor M. Alvarez',
    author_email='plusvic@gmail.com;vmalvarez@virustotal.com',
    url='https://github.com/VirusTotal/yara-python',
    zip_safe=False,
    cmdclass={'build': BuildCommand})
