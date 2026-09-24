--Primero se deben borrar todas las tablas (de detalle a maestro) y lugo anyadirlas (de maestro a detalle)

drop table if exists Employee;
drop table if exists Company;

create table Company (id int not null primary key, id2 int, name varchar(32), startDate varchar(10));
create table Employee (id int not null primary key, name varchar(32), 
                       salary int, birthDate varchar(10), idCompany int not null,
                       foreign key (idCompany) references Company (id), check (birthDate<"2010-01-01")
                      );

