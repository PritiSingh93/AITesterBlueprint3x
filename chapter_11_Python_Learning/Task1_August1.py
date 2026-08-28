# ✅ Grade Calculator:
# Write a program that calculates and displays the letter grade
# for a given numerical score (e.g., A, B, C, D, or F)
# based on the following grading scale
# A: 90-100
# B: 80-89
# C: 70-79
# D: 60-69
# F: 0-59

grade = int(input("Enter your grade from (0-100)"))

if grade >= 90 and grade <= 100:
    print("A")
elif grade >= 80 and grade <= 89:
    print("B")
elif grade >= 70 and grade <= 79:
    print("C")
elif grade >= 60 and grade <= 69:
    print("D")
elif grade >=0 and grade <= 59:
    print("F")
else:
    print("Invalid Input")   