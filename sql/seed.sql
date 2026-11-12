USE aiims_connect;
INSERT IGNORE INTO branch(Branch_ID,Branch_Name,City,Is_Main) VALUES(1,'AIIMS New Delhi','New Delhi',1),(2,'AIIMS Jodhpur','Jodhpur',0),(3,'AIIMS Bhubaneswar','Bhubaneswar',0);
INSERT IGNORE INTO department(Dept_ID,Branch_ID,Dept_Name) VALUES(1,1,'General Medicine'),(2,1,'Cardiology'),(3,2,'General Medicine'),(4,2,'Cardiology'),(5,3,'General Medicine'),(6,3,'Paediatrics');
INSERT IGNORE INTO ward(Ward_ID,Branch_ID,Ward_Name,Ward_Type,Total_Beds,Available_Beds,Daily_Rate) VALUES(1,1,'Delhi General','General',30,30,1800),(2,1,'Delhi ICU','ICU',8,8,6500),(3,2,'Jodhpur General','General',20,20,1500),(4,2,'Jodhpur ICU','ICU',5,5,5500),(5,3,'Bhubaneswar General','General',18,18,1400),(6,3,'Bhubaneswar ICU','ICU',4,4,5000);
