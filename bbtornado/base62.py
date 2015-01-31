import string

chars = string.digits + string.ascii_letters
base = len(chars)


def encode(num):
    '''Encode number in base62, returns a string.'''
    if num < 0:
        raise ValueError('cannot encode negative numbers')

    if num == 0:
        return chars[0]

    digits = []
    while num:
        rem = num % base
        num = num // base
        digits.append(chars[rem])
    return ''.join(reversed(digits))


def decode(string):
    '''Decode a base62 string to a number.'''
    loc = chars.index
    size = len(string)
    num = 0

    for i, ch in enumerate(string, 1):
        num += loc(ch) * (base ** (size - i))

    return num
