"""
seed_actual_data_final.py
--------------------------------------------------
Inserts ONLY the actual data extracted from the provided images.
Fixed: Added fallback logic for NOT NULL phone constraint.
"""

import random
from werkzeug.security import generate_password_hash
from app import app, get_db, generate_unique_id, DEFAULT_PASSWORD

# Data format: (Name, DOB (YYYY-MM-DD), Father's Name, Mother's Name, Aadhar, Mobile)
ACTUAL_DATA = {
    "1st": [
        ("Ayush Kumar", None, None, None, None, None),
        ("Aryan", None, None, None, None, None),
        ("Piyush", None, None, None, None, None),
        ("Rishabh", None, None, None, None, None),
        ("Sailesh", None, None, None, None, None),
        ("Divyanshu", None, None, None, None, None),
        ("Rishabh", None, None, None, None, None),
        ("Nimesh", None, None, None, None, None),
        ("Abham", None, None, None, None, None),
        ("Aditya", None, None, None, None, None),
        ("Mikku", None, None, None, None, None),
        ("Rudra", None, None, None, None, None),
        ("Prince", None, None, None, None, None),
        ("Saurabh", None, None, None, None, None),
        ("Abhiraj", None, None, None, None, None),
        ("Adit", None, None, None, None, None),
        ("Aditya", None, None, None, None, None),
        ("Pihu Kumari", None, None, None, None, None),
        ("Pari", None, None, None, None, None),
        ("Divya", None, None, None, None, None),
        ("Ritika", None, None, None, None, None),
        ("Mamta", None, None, None, None, None),
        ("Sonam", None, None, None, None, None),
        ("Khushboo", None, None, None, None, None),
        ("Nayra", None, None, None, None, None),
        ("Naiyra", None, None, None, None, None),
        ("Samekshidi", None, None, None, None, None),
        ("Anushka", None, None, None, None, None),
        ("Sweeta", None, None, None, None, None),
        ("Muskan", None, None, None, None, None),
        ("Manvi", None, None, None, None, None),
        ("Pihu", None, None, None, None, None),
        ("Somya", None, None, None, None, None),
        ("Anchal", None, None, None, None, None),
        ("Divyamshi", None, None, None, None, None),
        ("Abam Shahzada", None, None, None, None, None),
        ("Aryan Kumar", None, None, None, None, None),
        ("Indu Kumari", None, None, None, None, None),
        ("Abhay Kumar", None, None, None, None, None),
        ("Badal", None, None, None, None, None),
        ("Mahira", None, None, None, None, None),
        ("Aaradhya Kumari", None, None, None, None, None),
        ("Komal", None, None, None, None, None),
        ("Deepak Kumar", None, None, None, None, None),
        ("Ansh", None, None, None, None, None),
        ("Srishti Kumari", None, None, None, None, None),
        ("Munna Kumar", None, None, None, None, None),
        ("Sakshi Kumari", None, None, None, None, None),
        ("Vikash Kumar", None, None, None, None, None),
    ],
    
    "5th": [
        ("Bhavya Singh", None, "Punit Kumar", "Jyoti Singh", None, "9006515044"),
        ("Ragini Kumari", None, "Ravindra yadav", "Nibha kum", None, "7631958310"),
        ("Puja Kumari", None, "Brijmohan Pandit", "Rubi devi", None, "9693777340"),
        ("Nikhush Kumar", None, "Mukesh Pd", "Lilam devi", None, "9668057158"),
        ("Piyush", None, "Dheeraj mahto", "Sulekha devi", None, "9636494839"),
        ("Prashant Kumar", None, "Dinesh yadav", "Renu devi", None, "7870473792"),
        ("Sandhya Kumari", None, "Niraj Singh", "Ankita devi", None, "6381265528"),
        ("Nikhil Kumar", None, "Lal Babu Mandal", "Sani devi", None, "6206041594"),
        ("Priti Kumari", None, "Anmol Singh", "Rita devi", None, "7631625070"),
        ("Siddhi", None, "Ranjit Rawat", "Chandni kum", None, "9265217754"),
        ("Satyam Kumar", None, "Shankar das", "Savita devi", None, "9608713081"),
        ("Nandani Kumari", None, "Rakesh Saw", "Babita devi", None, "9625101416"),
        ("Ansh Kumar", None, "Anant Rawat", "Kajal devi", None, "8406085207"),
        ("Manjit Kumar", None, "Manoj yadav", "Laxmi devi", None, None),
        ("Ranjan Kumar", None, "Devendra mandal", "Rakhi Kumari", None, "7033285352"),
        ("Govind", None, "Pinku chaudhary", "Sruchi devi", None, "9004446170"),
        ("Kush Kumar", None, "Ram mandal", "Sita devi", None, "8238630738"),
        ("Suman", None, "Pawan Sharma", "J.T. Devi", None, "9006642770"),
        ("Rakhi Kumari", None, "Rajesh Rawat", "Chandani kn", None, "9265217754"),
        ("Piyush Kumar", None, "Bamki Sao", "Nibha devi", None, "7051240147"),
        ("Prince", None, "Sunil Gupta", "Kism devi", None, "7642834195"),
        ("Sonam Kumari", None, "Rajesh yadav", "Renu devi", None, None),
        ("Priyanshu Kumar", None, "Ravi Ram", "Jyanti devi", None, "9153658033"),
        ("Kadyan", None, "Rajesh yadav", "Nitu devi", None, "7766043470"),
        ("Kirtan", None, "Om Prakash", "Sonali devi", None, "7717412796"),
        ("Sushant", None, "Pawan Sao", "Babita devi", None, "9709502113"),
        ("Ashish Kumar", None, "Ajit tanti", "Jyoti devi", None, "977141296"),
        ("Ankush", None, None, "Rinku devi", None, None),
        ("Keshav", None, "Vidyadhar Singh", None, None, None),
        ("Aryan", None, None, None, None, None),
        ("Balaji", None, "Mukesh Singh", "Sanchita devi", None, "7738124564"),
        ("Kaushal", None, "Ramashish ya", "Sarita devi", None, "9122499192"),
        ("Piyush", None, "Raghunath", None, None, "7953866170"),
        ("Ankit", None, "Ripin mandal", "Kukumari devi", None, "8428201655"),
        ("Ishika Kumari", None, "Chhotu Sao", "Nibha devi", None, "6206042770"),
        ("Raju Kumari", None, "Raj kumar", "Sita devi", None, "7825277910"),
        ("Ruch Kumari", None, "Munnu mandal", "Munnu devi", None, "8107581970"),
        ("Subham", None, "Pramod Singh", "Nisha devi", None, "6202492770"),
        ("Monu Kumar", None, "Mangal mandal", "Rajni devi", None, None),
        ("Sonu Kumar", None, "Dharmendra", "Sunita devi", None, None),
    ],
    
    "LKG": [
        ("Punit Kumar", "2017-04-09", "Pintu", "Radhi Ka dev", "284173172768", "9599653190"),
        ("Pritam", "2018-05-08", None, None, None, None),
        ("Aradhya Kumari", "2017-07-10", "Bihari pandey", "Nitu kumari", None, "620330574"),
        ("Rajveer Kumari", "2018-02-12", "Munna saw", "Sanju devi", "760251615248", "9199255871"),
        ("Shruti Kumari", None, None, None, None, None),
        ("Rishi Kumar", "2018-03-06", "Mani chandra", "Srikri devi", "509592363845", "9431096370"),
        ("Ritesh", None, None, None, None, None),
        ("Ansh", "2017-08-11", "Rahul pandey", "Puja devi", None, "6299791815"),
        ("Misti Kumari", "2018-09-11", None, None, None, None),
        ("Alfe Khan", "2015-07-10", None, None, None, None),
        ("Shivam", "2016-10-26", None, None, None, None),
        ("Anushka Kumari", None, None, None, None, None),
        ("Sudhanshu Kumar", None, None, None, None, None),
        ("Hiralal", "2017-01-17", "Anandi chauhan", "Hema Devi", "966674201719", None),
        ("Shivansh", None, None, None, None, None),
        ("Vishnu", "2016-06-10", "Shrikant Sao", "Rubi devi", "315084974134", "703499205"),
        ("Anushka Kumari", "2017-07-10", "Dhiraj mandal", "Sulekha devi", "63835752098", "9636494839"),
        ("Shivam Kumar", "2017-01-10", "Arvind Rawat", "Soni devi", "94370779991", "8252728218"),
        ("Sristi Kumari", "2017-04-04", "Satyajit yadav", "Ruchi devi", None, None),
        ("Rani Kumari", "2014-04-28", "Pappu mistri", "Jitni Devi", "21382613933", None),
        ("Rriti", "2017-08-10", "Adhik Kumar", "Mamta kumari", "519449871148", "9006642790"),
        ("Aditya Kumar", "2017-07-16", "Pramod Rawat", "Laxmi devi", "860117821907", "7261898764"),
        ("Shistka Kumari", "2019-08-05", None, None, None, None),
        ("Satyam Kumar", "2019-08-20", "Anil singh", None, "371899945015", "7997349447"),
        ("Aryan Kumar", "2018-11-23", "Heeralal Rawat", "Rani devi", "72577159301", "7631625870"),
        ("Arushi Kumari", None, None, None, None, None),
        ("Rudra Kumar", None, None, None, None, None),
        ("Md. Sarzil", "2019-12-17", "md mustakim", "Sohzadi", "76805454484", None),
        ("Satyam Kumar", "2016-01-01", None, None, None, None),
        ("Jay Raman", "2018-06-27", None, None, None, None),
        ("Aman Kumar", None, None, None, None, None),
        ("Suman Kumar", "2019-05-24", "Mukesh Kumar", "Samdevi", "480109123861", "7462045797"),
        ("Ganesh Kumar", "2017-05-04", "Pawan chandra", "Sita devi", "801298736907", None),
        ("Rajveer", None, None, None, None, None),
        ("Satyam Kumar", None, None, None, None, None),
        ("Nandan", "2015-02-28", "Surandha Devi", None, "98264453742", "7596834082"),
        ("Shivani Kumari", "2017-07-26", "Shambhu Saw", "Shus devi", "52443399235", None),
        ("Priti", "2016-10-28", "Rajendra Sao", "Pramila devi", "67989348214", "9102624878"),
        ("Rohani Kumari", "2016-11-25", "Ranjit Kumar", "Madhuri devi", "45907492945", "8537775728"),
        ("Anand Kumar", None, None, None, None, None),
        ("Aradhya Kumari", "2017-12-01", "Laddu yadav", "Anita devi", None, "8292048584"),
        ("Sakshi Kumari", "2017-08-01", "Shail sir", "Sunita devi", "612870981643", "9490096577"),
        ("Gulshan Kumar", "2016-12-18", "Dilip chaudhary", "Babita devi", "968762672723", "8782979784"),
        ("Priyanshu Kumar", None, "Umeshkumar", "Babita devi", None, "6200571794"),
    ],
    
    "3rd": [
        ("Pintu Kumar", None, "Chandradev Yadav", "Sudha devi", None, "6206488073"),
        ("Rishav", None, "Sunil Yadav", "Renu Devi", None, "6200666415"),
        ("Anushka Kumari", "2016-05-08", "Kundan Kumar", "Arti Devi", "71388662296", "8825151034"),
        ("Aisha", "2016-08-17", "Kundan Kumar", "Arti Devi", "77477474130", "8825151034"),
        ("Ayush Kr Raj", None, None, None, None, None),
        ("Pihu Kumari", None, None, None, None, None),
        ("Abhisek Kumar", "2016-12-05", "Tuntun Sharma", "Ramli devi", "94381051755", "9631865970"),
        ("Arfat Afjal", "2015-07-23", "Md Afjal", "Shabnam khatoon", "29546783441", "7070077365"),
        ("Nazeer Hasan", None, None, None, None, None),
        ("Chhoti Kumari", "2016-05-24", "Ram Mandal", "Sita Devi", "37824082086", "9593905796"),
        ("Kartik Kumar", "2014-08-21", "Arvind Mandal", "Sindhu devi", "46431517165", "7739606014"),
        ("Shivam", "2016-02-23", "Pawan Kumar", "Kusum devi", "33335233638", "9122938500"),
        ("Sonam Kumar", "2018-06-20", "Chandan Mandal", "Sindhu Devi", "358464610356", "773866014"),
        ("Chandra Shekhar Kumar", None, None, None, None, None),
        ("Ayush Kumar", "2018-03-10", "Umesh Sao", "Indu devi", "727455565083", "7030446381"),
        ("Sakshi Kumari", "2019-09-01", "Sagar Kumar", None, "910538211930", "619301930"),
        ("Prashant Kumar", "2015-06-24", "Manish Mandal", "Manish Mandal", "94841190241", None),
        ("Navya Singh", None, "Deman pu", "Martina devi", None, None),
        ("Anushka Kumari", "2017-12-01", None, None, "70267300612", None),
        ("Rukmani", None, None, None, None, None),
        ("Sonu Kumar", None, None, None, None, None),
        ("Sandil", "2016-01-01", "Sushil Kumar", None, "25684785444", "6200475986"),
        ("Arnav Kumar", None, None, None, None, None),
        ("Aradhana", "2016-02-07", "Lal yadav", None, "837564824000", None),
        ("Santona Kumari", None, None, None, None, None),
        ("Chhoti", None, None, None, None, None),
        ("Gaurav Kumar", "2015-06-20", "Awadh Sao", None, "200028861152", None),
        ("Ritu Raj", None, None, None, None, None),
        ("Rajveer Kumar", None, None, None, None, None),
        ("Saurav", "2015-06-20", "Awadh Sao", None, "40526469717", None),
        ("Ujjawal Anand", "2016-04-14", None, None, None, None),
        ("Raju Kumar", None, None, None, None, None),
        ("Sona kumari", None, None, None, None, None),
        ("Abhisek Kumar", "2018-02-01", "Mukesh Saw", None, "730868488611", None),
        ("Sonuya kumari", "2017-03-22", "Santosh kumar", None, "606953093458", None),
        ("Larya Kumari", None, None, None, None, None),
        ("Prince Kumar", "2013-06-01", "Rajesh rawat", None, "66838953103", None),
        ("Kanhaiya Kumar", "2012-06-01", "Rajesh rawat", None, "712441600612", None),
        ("Vikash kumar", "2013-08-01", "Shree Narayan", None, "465336297614", None),
    ],
    
    "2nd": [
        ("Omjit Kumar", None, "Mukesh yadav", "Mamita devi", None, "9060831791"),
        ("Chahat", "2016-01-27", "Ashok yadav", "Sita devi", "741773226494", "8936847745"),
        ("Sintu", "2015-08-16", "Jayram", "Ruchi", "471594450678", "7541047901"),
        ("Vishal", "2014-10-31", "Chandradev", "Sudha", "800702986035", "6206488073"),
        ("Sweta Kumari", "2014-06-17", "Tuntun Sharma", "Punju devi", "466734958262", "9631695790"),
        ("Suman Kumari", "2017-01-17", "Ganesh chaw", "Pinki devi", "649334840312", "9572087160"),
        ("Chandani", "2015-02-05", "Ganesh chaw", "Pinki devi", "331251123809", None),
        ("Piyush Kumar", "2014-10-10", "Chandan chaw", "Lalita devi", "982988113601", "9896303562"),
        ("Alisama Praveen", None, "Umesh yadav", "Pramila devi", None, "9931546196"),
        ("Guddu Kumar", "2014-01-18", "md osman", "Nuri Naj", "212690642893", None),
        ("[Kumari]", None, "Salendra Saw", "Tushi devi", None, "9102624878"),
        ("Anushka", None, None, None, None, None),
        ("Labh Kumar", "2014-09-16", "Pawan Sao", "Pratima devi", "632079728477", "8340136639"),
        ("Mariya Kumari", None, "Rajendra Saw", "Priyanka devi", None, "8002354931"),
        ("Agam Kumar", None, None, None, None, None),
        ("Amit", "2016-12-25", "Ajeet Sao", "Bindu devi", "912408265555", "9570311470"),
        ("Ghanshyam Kumar", "2011-07-15", "Balmiki Sao", "Nibha devi", "659368020349", "7215322047"),
        ("Shidhant", None, "Salamdra mandal", "Soni devi", "294797827945", "9263967466"),
        ("Divyanshu Kumar", "2014-09-04", "Dinesh mahto", "Jayanti devi", "898258882552", "9661608220"),
        ("Sonu Verma", "2018-11-19", "Sabadh Kr Sao", "Sangita devi", "530675782467", "9193926172"),
        ("Alok Kumar", "0000-01-06", "Abadh Saw", "Kabita devi", "548287779864", "8002746614"),
    ],
    
    "7th": [
        ("Rishika Kumari", "2015-11-21", "Pintu mandal", "Radhika mau", "302228093195", "9599653190"),
        ("Devansh Kumar", "2017-12-14", "Dinanath tanti", "Pinki devi", "52235710744", "8877256923"),
        ("Rishu", "2012-06-29", "Sonu mandal", "Soni devi", "428606006795", "7482939464"),
        ("Shashikant Kumar", "2013-09-18", "Amit Pandit", "Anita devi", "281949916410", "6201233197"),
        ("Rovin Roy", "2016-03-21", "Ravindra yadav", "Nisha Kumari", "778130729701", "7631958310"),
        ("[Cut]", None, "Sunil Kumar", "Renu Kumari", None, "6200666415"),
        ("Navnit", "2015-04-08", "Shyam Singh", "Rakhi dev", None, "7631931267"),
        ("Subham", "2015-05-10", "Dileep mahto", "Rubi devi", "870822139731", "8292043594"),
        ("Rajnandani Kumari", "2015-09-17", "Jayram Verma", "Hemanti Vish", "873298689307", "9546810294"),
        ("Arushi Kumari", None, "Rahul pandey", "Puja devi", None, "6299791815"),
        ("Pratibha", None, "Shivkumar", "Babi devi", None, "8235905494"),
        ("Prince Kumar", None, None, None, None, None),
        ("[Cut]", None, None, None, None, None),
        ("Harimandan Kumar", None, "Ramashish pd", "Sarita devi", None, "9350499342"),
        ("Saloni Kumari", "2014-07-25", "Saner Ram", "Savita", "897273293095", "7541848041"),
        ("[Cut] Kumar", "2011-04-23", "Pd Dayal Sharma", "Jitani devi", "964813523357", "9006642790"),
        ("[Cut]", "2015-03-19", "Bighu kumar", "Nitu devi", "35861498157", "620330576"),
        ("Nitish Kumar", "2013-07-03", "Ashok tanti", "Archana devi", "28194991894", "9544828217"),
        ("Navroj", None, "Sunil Gupta", "Rima Kumari", None, "9693001920"),
        ("Anjali", None, "Santosh Mishra", "[Cut] devi", "271046459963", "9319278712"),
        ("Labh Kumar", "2013-02-05", "Ram mandal", "Sita devi", "701868986637", "9522905396"),
        ("[Cut] Ray", None, "Anil Kumar", "Parita kumari", None, "8340250504"),
        ("Sonay Verma", "2015-01-01", "Chand Verma", "Sharda Verma", "226155150664", "8107080002"),
    ],
    
    "8th": [
        ("PARNIT KUMAR", "2014-02-01", "Sunil Kumar", "Jyoti Singh", "767520193596", "9006515041"),
        ("ARUSHI KUMARI", "2013-02-25", "Santosh Sah", "Rekha devi", "76826192484", "8920695426"),
        ("ALSEHAT PARVEEN", "2013-08-16", "Afrroz Jab", "Noorjaha", "466607515358", "7853050513"),
        ("MUSKAN KUMARI", "2012-01-12", "Ram mandal", "Sita Devi", "21189836257", "8298670738"),
        ("DIVYANSHU RAJ", "2017-01-05", "Deenanath", "Pinki kumari", "37385362081", "8877256323"),
        ("AKANKSHA BHARATI", "2013-06-28", "Dharmendra", "Sunita devi", "738846550122", "9801037379"),
        ("RUPAM KUMARI", "2014-07-13", "Ramashish yadav", "Sarita devi", "90508281332", "9350492192"),
        ("AYUSH KUMAR", "2013-07-15", "Rahul pandey", "Puja devi", "30133311697", "6299991815"),
        ("FARHANA", "2011-02-02", "Md Ikbal", "Akhtar Parveen", "830858655279", "6206240345"),
        ("RAJVEER KUMAR", "2014-02-21", "Pinku Singh", "Hamanti devi", "882537993588", "9546810294"),
        ("RAUNAK KUMAR", "2015-02-02", "Deepak Saw", "Rakhi devi", "868567268135", "8797129906"),
        ("RIYA KUMARI", "2014-01-12", "Naresh Saw", "Srita devi", "85922011198", "7870474595"),
        ("JULI KUMARI", "2011-01-25", "Avinash mandal", "Kalpana devi", "84530602233", "7759909613"),
        ("GAURAV KUMAR", "2015-12-03", "Ravishankar Saw", "Soni devi", "873461170952", "9955000430"),
        ("SAURAV KUMAR", None, "Sushil Kumar", "Mamta devi", None, "8051992259"),
        ("MAHI RANI", "2015-02-02", "Aditya kumar", "Pratima kumari", None, "9091822329"),
        ("Sumit kumar", "2013-06-30", "Sushil kumar", "Shabnam devi", "682849964752", "8340136629"),
        ("Pallivi Kumari", "2013-08-30", "Pawan kumar", "Pratima devi", None, "8340136629"),
        ("Aayushi Kumari", None, None, None, None, None),
        ("Mahi Kumari", None, None, None, None, None),
        ("Drishtat Parveen", None, None, None, None, None),
        ("Aditya Kumar", None, None, None, None, None),
        ("Abuzar Kumar", None, None, None, None, None),
    ]
}

# यह सेट ट्रैक रखेगा कि कौन से फोन नंबर यूज़ हो चुके हैं
used_phones = set()

def get_safe_phone(db, phone):
    # अगर असली फोन नंबर है और डुप्लीकेट नहीं है
    if phone and str(phone) not in used_phones:
        if not db.execute('SELECT 1 FROM users WHERE phone = ?', (str(phone),)).fetchone():
            used_phones.add(str(phone))
            return str(phone)
    
    # अगर फोन नंबर नहीं है या डुप्लीकेट है, तो यूनिक 9XXXXXXXXX बनाओ
    while True:
        fallback = str(random.randint(9000000000, 9999999999))
        if fallback not in used_phones:
            if not db.execute('SELECT 1 FROM users WHERE phone = ?', (fallback,)).fetchone():
                used_phones.add(fallback)
                return fallback

def insert_data(db):
    created_students, created_parents = 0, 0
    
    for cls, students in ACTUAL_DATA.items():
        if not students:
            continue
            
        for roll, (name, dob, father, mother, aadhar, phone) in enumerate(students, start=1):
            
            # 1. Unique Email
            clean = ''.join(c for c in name.lower() if c.isalnum())
            base = f"{clean}.{cls.lower()}{roll}@student.snv.edu"
            email, i = base, 1
            while db.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone():
                i += 1
                email = base.replace('@', f".{i}@")

            # 2. Safe Phone Number (Handles NOT NULL)
            safe_phone = get_safe_phone(db, phone)

            # 3. Aadhar handle (agar duplicate ho toh None kar do)
            if aadhar and db.execute('SELECT 1 FROM users WHERE aadhar = ?', (aadhar,)).fetchone():
                aadhar = None

            uid = generate_unique_id('student')
            
            # Gender logic
            gender = "Female" if "kumari" in name.lower() or "devi" in name.lower() or "bharti" in name.lower() or "parveen" in name.lower() else "Male"
            
            # Section Logic
            section = 'A' if roll <= 25 else 'B'

            # 4. Insert Student
            db.execute("""
                INSERT INTO users
                  (unique_id, role, name, email, phone, password_hash, force_password_change, 
                   dob, gender, class_name, child_class, section, child_section, roll_no, 
                   admission_no, admission_date, father_name, mother_name, aadhar, nationality)
                VALUES (?, 'student', ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, '2025-04-01', ?, ?, ?, 'Indian')
            """, (uid, name, email, safe_phone, generate_password_hash(DEFAULT_PASSWORD), 
                  dob, gender, cls, cls, section, section, str(roll), uid, father, mother, aadhar))
            
            created_students += 1

            # 5. Insert Parent (Only if father name is present)
            if father:
                p_uid = generate_unique_id('parent')
                p_email = f"parent.{uid.lower()}@snv.edu"
                
                # Parent ke liye bhi safe phone generate karo (student ka safe_phone use kar sakte hain)
                db.execute("""
                    INSERT INTO users
                      (unique_id, role, name, email, phone, password_hash, force_password_change, 
                       relation, child_name, child_class, child_section, child_admission_no, child_dob)
                    VALUES (?, 'parent', ?, ?, ?, ?, 1, 'Father', ?, ?, ?, ?, ?)
                """, (p_uid, father, p_email, safe_phone, generate_password_hash(DEFAULT_PASSWORD),
                      name, cls, section, uid, dob))
                created_parents += 1

    db.commit()
    print(f"✅ Successfully Inserted {created_students} Students & {created_parents} Parents from Actual Data.")

if __name__ == '__main__':
    with app.app_context():
        print("Connecting to DB...")
        db = get_db()
        insert_data(db)
        print("Done! All actual data inserted successfully.")