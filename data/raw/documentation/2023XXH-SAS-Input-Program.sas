/****************************************************************************************/
/*  This SAS program reads ASCII format (text format) 2023 YRBS data and creates a      */
/*  formatted and labeled SAS dataset.                                                  */
/*                                                                                      */
/*  Change the file location specifications from 'c:\YRBS2023' to the location where    */
/*  you have stored the YRBS ASCII data file and the format library before you run this */
/*  program.  Change the location specification in three places - in the 'filename'     */
/*  statement and in the two 'libname' statements at the top of the program.            */
/*                                                                                      */
/*  Note: Run '2023XXH Formats Program.sas' BEFORE you run                              */
/*  '2023XXH SAS Input Program.sas' to create the 2023YRBS dataset.                    */
/****************************************************************************************/
 
filename datain 'c:\yrbs2023\XXH2023_YRBS_DATA.dat';
libname dataout 'c:\yrbs2023';
libname library 'c:\yrbs2023';
data dataout.yrbs2023 ;
infile datain lrecl=500;
Input
@17 Q1 $1.
@18 Q2 $1.
@19 Q3 $1.
@20 Q4 $1.
@21 Q5 $8.
@29 Q6 4.2
@33 Q7 6.2
@39 Q8 $1.
@40 Q9 $1.
@41 Q10 $1.
@42 Q11 $1.
@43 Q12 $1.
@44 Q13 $1.
@45 Q14 $1.
@46 Q15 $1.
@47 Q16 $1.
@48 Q17 $1.
@49 Q18 $1.
@50 Q19 $1.
@51 Q20 $1.
@52 Q21 $1.
@53 Q22 $1.
@54 Q23 $1.
@55 Q24 $1.
@56 Q25 $1.
@57 Q26 $1.
@58 Q27 $1.
@59 Q28 $1.
@60 Q29 $1.
@61 Q30 $1.
@62 Q31 $1.
@63 Q32 $1.
@64 Q33 $1.
@65 Q34 $1.
@66 Q35 $1.
@67 Q36 $1.
@68 Q37 $1.
@69 Q38 $1.
@70 Q39 $1.
@71 Q40 $1.
@72 Q41 $1.
@73 Q42 $1.
@74 Q43 $1.
@75 Q44 $1.
@76 Q45 $1.
@77 Q46 $1.
@78 Q47 $1.
@79 Q48 $1.
@80 Q49 $1.
@81 Q50 $1.
@82 Q51 $1.
@83 Q52 $1.
@84 Q53 $1.
@85 Q54 $1.
@86 Q55 $1.
@87 Q56 $1.
@88 Q57 $1.
@89 Q58 $1.
@90 Q59 $1.
@91 Q60 $1.
@92 Q61 $1.
@93 Q62 $1.
@94 Q63 $1.
@95 Q64 $1.
@96 Q65 $1.
@97 Q66 $1.
@98 Q67 $1.
@99 Q68 $1.
@100 Q69 $1.
@101 Q70 $1.
@102 Q71 $1.
@103 Q72 $1.
@104 Q73 $1.
@105 Q74 $1.
@106 Q75 $1.
@107 Q76 $1.
@108 Q77 $1.
@109 Q78 $1.
@110 Q79 $1.
@111 Q80 $1.
@112 Q81 $1.
@113 Q82 $1.
@114 Q83 $1.
@115 Q84 $1.
@116 Q85 $1.
@117 Q86 $1.
@118 Q87 $1.
@119 Q88 $1.
@120 Q89 $1.
@121 Q90 $1.
@122 Q91 $1.
@123 Q92 $1.
@124 Q93 $1.
@125 Q94 $1.
@126 Q95 $1.
@127 Q96 $1.
@128 Q97 $1.
@129 Q98 $1.
@130 Q99 $1.
@131 Q100 $1.
@132 Q101 $1.
@133 Q102 $1.
@134 Q103 $1.
@135 Q104 $1.
@136 Q105 $1.
@137 Q106 $1.
@138 Q107 $1.
@185 QN8 1.
@186 QN9 1.
@187 QN10 1.
@188 QN11 1.
@189 QN12 1.
@190 QN13 1.
@191 QN14 1.
@192 QN15 1.
@193 QN16 1.
@194 QN17 1.
@195 QN18 1.
@196 QN19 1.
@197 QN20 1.
@198 QN21 1.
@199 QN22 1.
@200 QN23 1.
@201 QN24 1.
@202 QN25 1.
@203 QN26 1.
@204 QN27 1.
@205 QN28 1.
@206 QN29 1.
@207 QN30 1.
@208 QN31 1.
@209 QN32 1.
@210 QN33 1.
@211 QN34 1.
@212 QN35 1.
@213 QN36 1.
@214 QN37 1.
@215 QN38 1.
@216 QN39 1.
@217 QN40 1.
@218 QN41 1.
@219 QN42 1.
@220 QN43 1.
@221 QN44 1.
@222 QN45 1.
@223 QN46 1.
@224 QN47 1.
@225 QN48 1.
@226 QN49 1.
@227 QN50 1.
@228 QN51 1.
@229 QN52 1.
@230 QN53 1.
@231 QN54 1.
@232 QN55 1.
@233 QN56 1.
@234 QN57 1.
@235 QN58 1.
@236 QN59 1.
@237 QN60 1.
@238 QN61 1.
@239 QN62 1.
@243 QN66 1.
@244 QN67 1.
@245 QN68 1.
@246 QN69 1.
@247 QN70 1.
@248 QN71 1.
@249 QN72 1.
@250 QN73 1.
@251 QN74 1.
@252 QN75 1.
@253 QN76 1.
@254 QN77 1.
@255 QN78 1.
@256 QN79 1.
@257 QN80 1.
@258 QN81 1.
@259 QN82 1.
@260 QN83 1.
@261 QN84 1.
@262 QN85 1.
@263 QN86 1.
@264 QN87 1.
@265 QN88 1.
@266 QN89 1.
@267 QN90 1.
@268 QN91 1.
@269 QN92 1.
@270 QN93 1.
@271 QN94 1.
@272 QN95 1.
@273 QN96 1.
@274 QN97 1.
@275 QN98 1.
@276 QN99 1.
@277 QN100 1.
@278 QN101 1.
@279 QN102 1.
@280 QN103 1.
@281 QN104 1.
@282 QN105 1.
@283 QN106 1.
@284 QN107 1.
@1 SITE $3.
@350 QNFRCIG 1.
@351 QNDAYCIG 1.
@352 QNFREVP 1.
@353 QNDAYEVP 1.
@354 QNFRSKL 1.
@355 QNDAYSKL 1.
@356 QNFRCGR 1.
@357 QNDAYCGR 1.
@358 QNTB2 1.
@359 QNTB3 1.
@360 QNTB4 1.
@361 QNTB5 1.
@362 QNIUDIMP 1.
@363 QNOTHHPL 1.
@364 QNDUALBC 1.
@365 QNBCNONE 1.
@366 QNFR0 1.
@367 QNFR1 1.
@368 QNFR2 1.
@369 QNVEG0 1.
@370 QNVEG1 1.
@371 QNVEG2 1.
@372 QNVEG3 1.
@373 QNSODA1 1.
@374 QNSODA2 1.
@375 QNBK7DAY 1.
@376 QNPA0DAY 1.
@377 QNPA7DAY 1.
@378 QNDLYPE 1.
@379 QNNODNT 1.
@380 QNSPDRK1 1.
@381 QNSPDRK2 1.
@382 QNWATER1 1.
@383 QNWATER2 1.
@384 QNWATER3 1.
@385 QNILLICT 1.
@386 QNOBESE 1.
@387 QNOWT 1.
@388 WEIGHT 10.4
@398 STRATUM 3.
@401 PSU 6.
@407 BMIPCT 5.2
@414 RACEETH $2.
@416 Q6ORIG $3.
@419 Q7ORIG $3.
;

/****************************************/
/*   Assign formats to SAS variables    */
/****************************************/
 
format
Q1 $H1S. Q2 $H2S. Q3 $H3S. Q4 $H4S. Q5 $char8. 
Q6 4.2 Q7 6.2 Q8 $H8S. Q9 $H9S. Q10 $H10S. 
Q11 $H11S. Q12 $H12S. Q13 $H13S. Q14 $H14S. Q15 $H15S. 
Q16 $H16S. Q17 $H17S. Q18 $H18S. Q19 $H19S. Q20 $H20S. 
Q21 $H21S. Q22 $H22S. Q23 $H23S. Q24 $H24S. Q25 $H25S. 
Q26 $H26S. Q27 $H27S. Q28 $H28S. Q29 $H29S. Q30 $H30S. 
Q31 $H31S. Q32 $H32S. Q33 $H33S. Q34 $H34S. Q35 $H35S. 
Q36 $H36S. Q37 $H37S. Q38 $H38S. Q39 $H39S. Q40 $H40S. 
Q41 $H41S. Q42 $H42S. Q43 $H43S. Q44 $H44S. Q45 $H45S. 
Q46 $H46S. Q47 $H47S. Q48 $H48S. Q49 $H49S. Q50 $H50S. 
Q51 $H51S. Q52 $H52S. Q53 $H53S. Q54 $H54S. Q55 $H55S. 
Q56 $H56S. Q57 $H57S. Q58 $H58S. Q59 $H59S. Q60 $H60S. 
Q61 $H61S. Q62 $H62S. Q63 $H63S. Q64 $H64S. Q65 $H65S. 
Q66 $H66S. Q67 $H67S. Q68 $H68S. Q69 $H69S. Q70 $H70S. 
Q71 $H71S. Q72 $H72S. Q73 $H73S. Q74 $H74S. Q75 $H75S. 
Q76 $H76S. Q77 $H77S. Q78 $H78S. Q79 $H79S. Q80 $H80S. 
Q81 $H81S. Q82 $H82S. Q83 $H83S. Q84 $H84S. Q85 $H85S. 
Q86 $H86S. Q87 $H87S. Q88 $H88XX. Q89 $H89XX. Q90 $H90XX. 
Q91 $H91XX. Q92 $H92XX. Q93 $H93XX. Q94 $H94XX. Q95 $H95XX. 
Q96 $H96XX. Q97 $H97XX. Q98 $H98XX. Q99 $H99XX. Q100 $H100XX. 
Q101 $H101XX. Q102 $H102XX. Q103 $H103XX. Q104 $H104XX. Q105 $H105XX. 
Q106 $H106XX. Q107 $H107XX. 
raceeth $HRCE.
;

/****************************************/
/*   Assign labels to SAS variables     */
/****************************************/
 
label
Q1="How old are you"
Q2="What is your sex"
Q3="In what grade are you"
Q4="Are you Hispanic/Latino"
Q5="What is your race"
Q6="How tall are you"
Q7="How much do you weigh"
Q8="Seat belt use"
Q9="Riding with a drinking driver"
Q10="Drinking and driving"
Q11="Texting and driving"
Q12="Weapon carrying at school"
Q13="Gun carrying"
Q14="Safety concerns at school"
Q15="Threatened at school"
Q16="Times in fight past 12 months"
Q17="Physical fighting at school"
Q18="Saw physical violence in neighborhood"
Q19="Ever been physically forced sexual intercourse"
Q20="Sexual violence"
Q21="Sexual dating violence"
Q22="Physical dating violence"
Q23="treated unfairly in school b/c race/ethnicity"
Q24="Bullied at school"
Q25="Electronic bullying"
Q26="Sad or hopeless"
Q27="Considered suicide"
Q28="Made a suicide plan past 12 months"
Q29="Actually attempted suicide"
Q30="Injurious suicide attempt"
Q31="Ever cigarette use"
Q32="Initiation of cigarette smoking"
Q33="Current cigarette use"
Q34="Smoked >10 cigarettes"
Q35="Electronic vapor product use"
Q36="Current electronic vapor product use"
Q37="EVP from store"
Q38="Current smokeless tobacco use"
Q39="Current cigar use"
Q40="All tobacco product cessation"
Q41="Initiation of alcohol use"
Q42="Current alcohol use"
Q43="Current binge drinking"
Q44="Drinks in a row past 30 days"
Q45="Source of alcohol"
Q46="Ever marijuana use"
Q47="Initiation of marijuana use"
Q48="Current marijuana use"
Q49="Ever prescription pain medicine use"
Q50="Ever cocaine use"
Q51="Ever inhalant use"
Q52="Ever heroin use "
Q53="Ever methamphetamine use"
Q54="Ever ecstasy use"
Q55="Illegal injected drug use"
Q56="Ever sexual intercourse"
Q57="Sex before 13 years"
Q58="Number of sex partners"
Q59="Current sexual activity"
Q60="Alcohol/drugs and sex"
Q61="Condom use"
Q62="Birth control pill use"
Q63="Sex of sexual contacts"
Q64="Sexual identity"
Q65="Transgender"
Q66="Perception of weight"
Q67="Weight loss"
Q68="Fruit juice drinking"
Q69="Fruit eating"
Q70="Green salad eating"
Q71="Potato eating"
Q72="Carrot eating"
Q73="Other vegetable eating"
Q74="No soda drinking"
Q75="Breakfast eating"
Q76="Physical activity >= 5 days"
Q77="PE attendance"
Q78="Sports team participation"
Q79="Concussion"
Q80="Social media"
Q81="HIV testing"
Q82="STD testing"
Q83="Oral health care"
Q84="Current mental health"
Q85="Hours of sleep on school night"
Q86="Unstable Housing"
Q87="Grades in school"
Q88="Ever sexual abuse by adult or older person ACEs"
Q89="Ever parental emotional abuse ACEs"
Q90="Ever parental physical abuse ACEs"
Q91="Adults in home intimate partner violence ACEs"
Q92="Current Rx Pain med w/out Rx"
Q93="Ever used hallucinogenic drugs"
Q94="If verbally asked for consent last sexual contact"
Q95="Sports drinks"
Q96="Plain water"
Q97="Muscle strengthening"
Q98="Sunburn"
Q99="How often household adult met basic needs ACEs"
Q100="Ever lived w/parent/guardian w/substance abuse ACE"
Q101="Ever lived with parent/guardian w mental illness A"
Q102="Ever incarcerated parent/guardian ACEs"
Q103="Feel close to people at their school"
Q104="Parental monitoring"
Q105="Unfairly disciplined at school"
Q106="Difficulty concentrating"
Q107="How well speak English"
QN8="Did not always wear a seat belt"
QN9="Rode with a driver who had been drinking alcohol"
QN10="Drove a car or other vehicle when they had been drinking alcohol"
QN11="Texted or e-mailed while driving a car or other vehicle	"
QN12="Carried a weapon on school property "
QN13="Carried a gun "
QN14="Did not go to school because they felt unsafe at school or on their way to or from school "
QN15="Were threatened or injured with a weapon on school property "
QN16="Were in a physical fight "
QN17="Were in a physical fight on school property "
QN18="Ever saw someone get physically attacked, beaten, stabbed, or shot in their neighborhood"
QN19="Were ever physically forced to have sexual intercourse"
QN20="Experienced sexual violence"
QN21="Experienced sexual dating violence"
QN22="Experienced physical dating violence"
QN23="Felt that they were ever treated badly or unfairly in school because of their race or ethnicity"
QN24="Were bullied on school property"
QN25="Were electronically bullied"
QN26="Felt sad or hopeless"
QN27="Seriously considered attempting suicide"
QN28="Made a plan about how they would attempt suicide"
QN29="Attempted suicide"
QN30="Had a suicide attempt that resulted in an injury, poisoning, or overdose that had to be treated by a doctor or nurse"
QN31="Ever smoked a cigarette"
QN32="Smoked a cigarette before age 13 years"
QN33="Currently smoked cigarettes"
QN34="Smoked more than 10 cigarettes per day"
QN35="Ever used an electronic vapor product"
QN36="Currently used an electronic vapor product"
QN37="Usually got their electronic vapor products by buying them themselves in a convenience store, supermarket, discount store, or gas station"
QN38="Currently used smokeless tobacco"
QN39="Currently smoked cigars"
QN40="Tried to quit using all tobacco products"
QN41="Had their first drink of alcohol before age 13 years"
QN42="Currently drank alcohol"
QN43="Currently were binge drinking"
QN44="Reported that the largest number of drinks they had in a row was 10 or more"
QN45="Usually got the alcohol they drank by someone giving it to them"
QN46="Ever used marijuana "
QN47="tried marijuana for the first time before age 13 years"
QN48="Currently used marijuana "
QN49="Ever took prescription pain medicine without a doctor's prescription or differently than how a doctor told them to use it"
QN50="Ever used cocaine "
QN51="Ever used inhalants"
QN52="Ever used heroin "
QN53="Ever used methamphetamines"
QN54="Ever used ecstasy"
QN55="Ever injected any illegal drug "
QN56="Ever had sexual intercourse"
QN57="Had sexual intercourse for the first time before age 13 years"
QN58="Had sexual intercourse with four or more persons during their life"
QN59="Were currently sexually active"
QN60="Drank alcohol or used drugs before last sexual intercourse"
QN61="Used a condom during last sexual intercourse"
QN62="Used birth control pills before last sexual intercourse with opposite-sex partner"
QN66="Described themselves as slightly or very overweight"
QN67="Were trying to lose weight"
QN68="Did not drink fruit juice"
QN69="Did not eat fruit"
QN70="Did not eat green salad"
QN71="Did not eat potatoes"
QN72="Did not eat carrots"
QN73="Did not eat other vegetables"
QN74="Did not drink a can, bottle, or glass of soda or pop "
QN75="Did not eat breakfast"
QN76="Were physically active at least 60 minutes per day on 5 or more days"
QN77="Attended physical education (PE) classes on 1 or more days"
QN78="Played on at least one sports team"
QN79="Had a concussion from playing a sport or being physically active"
QN80="Used social media several times a day"
QN81="Were ever tested for human immunodeficiency virus (HIV)"
QN82="Were ever tested for a sexually transmitted disease (STD)"
QN83="Saw a dentist"
QN84="Reported that their mental health was most of the time or always not good"
QN85="Got 8 or more hours of sleep"
QN86="Experienced unstable housing"
QN87="Described their grades in school as mostly A''s or B''s"
QN88="Reported that an adult or person at least 5 years older than them ever made them do sexual things they did not want to do"
QN89="Reported that a parent or other adult in their home most of the time or always insulted them or put them down"
QN90="Reported that a parent or other adult in their home most of the time or always hit, beat, kicked, or physically hurt them in any way"
QN91="Reported that their parents or other adults in their home most of the time or always slapped, hit, kicked, punched, or beat each other up"
QN92="currently took prescription pain medicine without a doctor's prescription or differently than how a doctor told them to use it"
QN93="ever used hallucinogenic drugs"
QN94="Verbally asked for consent the last time they had sexual contact"
QN95="did not drink a can, bottle, or glass of a sports drink"
QN96="did not drink a bottle or glass of plain water"
QN97="did exercises to strengthen or tone their muscles on three or more days"
QN98="had a sunburn"
QN99="Reported that an adult in their household most of the time or always tried to make sure their basic needs were met"
QN100="ever lived with a parent or guardian who was having a problem with alcohol or drug use"
QN101="ever lived with a parent or guardian who had severe depression, anxiety, or another mental illness, or was suicidal"
QN102="Have ever been separated from a parent or guardian because they went to jail, prison, or a detention center"
QN103="strongly agree or agree that they feel close to people at their school"
QN104="reported that their parents or other adults in their family most of the time or always know where they are going or with whom they will be"
QN105="have been unfairly disciplined at school"
QN106="have serious difficulty concentrating, remembering, or making decisions"
QN107="speak English well or very well"
site="Site Code"
qnfrcig="Currently smoked cigarettes frequently "
qndaycig="Currently smoked cigarettes daily"
qnfrevp="Currently used electronic vapor products frequently"
qndayevp="Currently used electronic vapor products daily"
qnfrskl="Currently used smokeless tobacco frequently"
qndayskl="Currently used smokeless tobacco daily"
qnfrcgr="Currently smoked cigars frequently"
qndaycgr="Currently smoked cigars daily"
qntb2="Currently smoked cigarettes or cigars"
qntb3="Currently smoked cigarettes or cigars or used smokeless tobacco"
qntb4="Currently smoked cigarettes or cigars or used smokeless tobacco or electronic vapor products"
qntb5="Currently smoked cigarettes or used electronic vapor products"
qniudimp="Used an IUD (such as Mirena or ParaGard) or implant (such as Implanon or Nexplanon) before last sexual intercourse with an opposite-sex partner"
qnothhpl="Used birth control pills; an IUD or implant; or a shot, patch, or birth control ring before last sexual intercourse with an opposite-sex partner"
qndualbc="Used both a condom during last sexual intercourse and birth control pills; an IUD or implant; or a shot, patch, or birth control ring before last sexual intercourse with an opposite-sex partner"
qnbcnone="Did not use any method to prevent pregnancy during last sexual intercourse with an opposite-sex partner"
qnfr0="Did not eat fruit or drink 100% fruit juices"
qnfr1="Ate fruit or drank 100% fruit juices one or more times per day"
qnfr2="Ate fruit or drank 100% fruit juices two or more times per day"
qnveg0="Did not eat vegetables"
qnveg1="Ate vegetables one or more times per day"
qnveg2="Ate vegetables two or more times per day"
qnveg3="Ate vegetables three or more times per day"
qnsoda1="Drank a can, bottle, or glass of soda or pop one or more times per day"
qnsoda2="Drank a can, bottle, or glass of soda or pop two or more times per day"
qnbk7day="Ate breakfast on all 7 days"
qnpa0day="Did not participate in at least 60 minutes of physical activity on at least 1 day"
qnpa7day="Were physically active at least 60 minutes per day on all 7 days"
qndlype="Attended physical education classes on all 5 days"
qnnodnt="Never saw a dentist"
qnspdrk1="Drank a can, bottle, or glass of a sports drink one or more times per day"
qnspdrk2="Drank a can, bottle, or glass of a sports drink two or more times per day"
qnwater1="Drank a bottle or glass of plain water one or more times per day"
qnwater2="drank a bottle or glass of plain water two or more times per day"
qnwater3="drank a bottle or glass of plain water three or more times per day"
qnillict="Ever used select illicit drugs"
qnobese="Had obesity"
qnowt="Were Overweight"
weight="Overall Analysis Weight"
stratum="Sampling Strata"
psu="Primary Sampling Unit"
bmipct="Body Mass Index Percentile"
raceeth="Race/Ethnicity"
q6orig="Original unedited student height"
q7orig="Original unedited student weight"
;
run;
