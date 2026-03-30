
def validate_tc_kimlik(tc_no: str) -> bool:
    tc_no = str(tc_no).strip().replace(" ", "")
    if len(tc_no) != 11 or not tc_no.isdigit():
        return False
    if tc_no[0] == '0':
        return False
    digits = [int(d) for d in tc_no]
    sum_odd = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
    sum_even = digits[1] + digits[3] + digits[5] + digits[7]
    tenth_digit = ((sum_odd * 7) - sum_even) % 10
    eleventh_digit = sum(digits[:10]) % 10
    return (digits[9] == tenth_digit and digits[10] == eleventh_digit)

test_cases = ["12345678950", "10000000146"]
for tc in test_cases:
    print(f"TC: {tc}, Valid: {validate_tc_kimlik(tc)}")
