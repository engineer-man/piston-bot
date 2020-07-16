import re


def codeswap(language, source):
    if language == 'java':
        return for_java(source)
    else:
        return source


def for_java(inp):
    out = ''

    if re.match('(\n|.)*(public class)(.|\n)*', inp):
        return inp

    lines = inp.split('\n')
    for line in lines:
        if line.lstrip().startswith('import'):
            out += line + '\n'

    out += 'public class temp extends Object'

    # for line in lines:
    #     if line.lstrip().startswith('extends'):
    #         line = line.replace(';', '')
    #         out += ', ' + line[line.index('extends ') + 8:]
    #         break

    out += ''' {
    public static void main(String[] args) {'''

    if 'extends' in inp:
        yup = False
        for line in lines:
            if 'extends' in line:
                yup = True
            elif yup:
                out += '        ' + line + '\n'
    elif 'import' in inp:
        for line in lines:
            if not line.startswith('import'):
                out += '        ' + line + '\n'
    else:
        for line in lines:
            out += '        ' + line + '\n'

    out += '    }\n}'

    return out
