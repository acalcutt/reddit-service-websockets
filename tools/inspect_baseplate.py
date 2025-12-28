import pkgutil
try:
    import baseplate
    print('baseplate:', getattr(baseplate, '__file__', '<built-in>'))
    print('submodules:')
    for mod in pkgutil.iter_modules(baseplate.__path__):
        print(' -', mod.name)
    print('attributes:', [a for a in dir(baseplate) if not a.startswith('__')][:200])
except Exception as e:
    print('error', e)
