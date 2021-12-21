name = 'dxusd'
version = '2.0.0'

requires = [
    'dxrulebook'
]

def commands():
    env.PATH.append('{root}/bin')
    env.PYTHONPATH.append('{root}/scripts')
