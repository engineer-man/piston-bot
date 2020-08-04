def add_boilerplate(language, source):
    if language == 'java':
        return for_java(source)
    elif language == 'rust':
        return for_rust(source)
    else:
        return source


def for_java(source):
    if 'public class' in source:
        return source

    imports = []
    code = [
        'public class temp extends Object {public static void main(String[] args) {']

    lines = source.replace(';', ';\n').split('\n')
    for line in lines:
        if line.lstrip().startswith('import'):
            imports.append(line)
        else:
            code.append(line)

    code.append('}}')
    return ''.join(imports + code)


def for_rust(source):
    if 'fn main' in source:
        return source
    imports = []
    code = ['fn main() {']

    lines = source.replace(';', ';\n').split('\n')
    for line in lines:
        if line.lstrip().startswith('use'):
            imports.append(line)
        else:
            code.append(line)

    code.append('}')
    return ''.join(imports + code)
