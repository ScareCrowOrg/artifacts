import sys
import coverage
print('file:', coverage.__file__)
print('has types:', hasattr(coverage, 'types'))
print('attrs:', [x for x in dir(coverage) if not x.startswith('_')])
