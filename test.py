from barcode import Code39   ### THE CODE USED ON SCHOOL ID'S

data = '444628464'   

my_code = Code39(data, add_checksum=False)

my_code.save('barcode')