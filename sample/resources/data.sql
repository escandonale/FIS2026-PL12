--Carga inicial de datos. Se cargan de maestro a detalle

--Company
insert into Company(id,id2,name,startDate) values(1,null,'Company 1','2020-05-03');
insert into Company(id,id2,name,startDate) values(3,3333,'Company 3','1999-12-24');
insert into Company(id,id2,name,startDate) values(2,2222,'Company 2','2013-01-23');
--Employee
insert into Employee (id,name,salary,birthDate,idCompany) values (1,'E1',2000,'2000-01-01',3);
insert into Employee (id,name,salary,birthDate,idCompany) values (2,'E2',3000,'1998-01-01',2);
insert into Employee (id,name,salary,birthDate,idCompany) values (3,'E3',1500,'2001-01-01',2);
insert into Employee (id,name,salary,birthDate,idCompany) values (4,'E4',1000,'2004-01-01',3);
insert into Employee (id,name,salary,birthDate,idCompany) values (5,'E5',4000,'1990-01-01',3);
insert into Employee (id,name,salary,birthDate,idCompany) values (6,'E6',1000,'2000-01-01',3);


