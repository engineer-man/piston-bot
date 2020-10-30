def add_boilerplate(language, source):
    if language == 'java':
        return for_java(source)
    if language == 'rust':
        return for_rust(source)
    if language == 'c' or language == 'cpp':
        return for_c_cpp(source)
    if language == 'go':
        return for_go(source)
    return source

def for_go(source):
    if 'main' in source:
        return source

    package = ['package main']
    imports = []
    code = ['func main() {']

    lines = source.split('\n')
    for line in lines:
        if line.lstrip().startswith('import'):
            imports.append(line)
        else:
            code.append(line)

    code.append('}')
    return '\n'.join(package + imports + code)

def for_c_cpp(source):
    if 'main' in source:
        return source

    imports = []
    code = ['int main() {']

    lines = source.replace(';', ';\n').split('\n')
    for line in lines:
        print(line)
        if line.lstrip().startswith('include'):
            imports.append(line)
        else:
            code.append(line)

    code.append('}')
    return '\n'.join(imports + code)


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
    return '\n'.join(imports + code)


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
    return '\n'.join(imports + code)
