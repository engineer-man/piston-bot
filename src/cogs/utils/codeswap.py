def add_boilerplate(language, source):
    if language == 'java':
        return for_java(source)
    else:
        return source


def for_java(source):
    if 'public class' in source:
        return source

    imports = []
    code = ['public class temp extends Object {public static void main(String[] args) {']

    lines = source.replace(';', ';\n').split('\n')
    for line in lines:
        if line.lstrip().startswith('import'):
            imports.append(line)
        else:
            code.append(line)

    code.append('}}')
    return ''.join(imports + code)
