data = open('tools/admin/validate_jurisdiction_fields.py', 'rb').read()
print('CRLF:', data.count(b'\r\n'), 'LF only:', data.count(b'\n') - data.count(b'\r\n'))
