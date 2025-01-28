import os
import shutil
from datetime import datetime
from decimal import Decimal
from models import Car, CarFullInfo, CarStatus, Model, ModelSaleStats, Sale
from sortedcontainers import SortedDict
from config import CARS, MODELS, SALES, CMS

class CarService:
    def __init__(self, root_directory_path: str) -> None:
        self.root_directory_path = root_directory_path
        self.__extend_file_size = 500
        self.__extend_index_size = 50
        self.__index_array = {}
        
        if os.path.exists(self.root_directory_path):
            shutil.rmtree(self.root_directory_path)
        os.makedirs(self.root_directory_path, exist_ok=True)
        
        for file in CMS:
            open(f'{self.root_directory_path}/{CMS[file]}', "a").close()
            open(f'{self.root_directory_path}/{CMS[file]}_index', "a").close()
        
        for name in CMS:
            self.__index_array[name] = SortedDict()

    # Задание 1. Сохранение автомобилей и моделей
    def add_model(self, model: Model) -> Model:
        model_data = (model.id, model.name, model.brand)
        self.__insert(MODELS, model_data, model.index())
        return model

    def add_car(self, car: Car) -> Car:
        car_data = (car.vin, car.model, car.price, car.date_start.isoformat(), car.status)
        self.__insert(CARS, car_data, car.index())
        return car
    
    # Задание 2. Сохранение продаж
    def sell_car(self, sale: Sale) -> Car:
        sale_data = (sale.sales_number, sale.car_vin, sale.sales_date.isoformat(), sale.cost)
        self.__insert(SALES, sale_data, sale.index())

        car_info = self.__get_data_by_field(CARS, sale.car_vin)
        if car_info:
            car_record, line_number = car_info
            car_fields = car_record.split(';')
            car = Car(
                vin=car_fields[0],
                model=int(car_fields[1]),
                price=Decimal(car_fields[2]),
                date_start=datetime.fromisoformat(car_fields[3]),
                status=CarStatus.sold
            )
            self.__update(CARS, (car.vin, car.model, car.price, car.date_start.isoformat(), car.status), line_number)
            return car
        return None
    
    # Задание 3. Доступные к продаже 
    def get_cars(self, status: CarStatus) -> list[Car]:
        available_cars = []
        with open(f'{self.root_directory_path}/{CMS[CARS]}', "r") as f:
            for line in f:
                car_fields = line.strip().split(';')
                if car_fields[4] == status:
                    car = Car(
                        vin=car_fields[0],
                        model=int(car_fields[1]),
                        price=Decimal(car_fields[2]),
                        date_start=datetime.fromisoformat(car_fields[3]),
                        status=CarStatus(car_fields[4])
                    )
                    available_cars.append(car)
        return available_cars
     
    # Задание 4. Детальная информация
    def get_car_info(self, vin: str) -> CarFullInfo | None:
        car_info = self.__get_data_by_field(CARS, vin)
        if not car_info:
            return None

        car_record, _ = car_info
        car_fields = car_record.split(';')
        model_info = self.__get_data_by_field(MODELS, car_fields[1])
        if not model_info:
            return None

        model_record, _ = model_info
        model_fields = model_record.split(';')

        sales_info = None
        if car_fields[4] == CarStatus.sold:
            sales_info = self.__get_data_sec_scan(CMS[SALES], vin)
            if sales_info:
                sales_fields = sales_info.split(';')
                sales_date = datetime.fromisoformat(sales_fields[2])
                sales_cost = Decimal(sales_fields[3])
            else:
                sales_date = None
                sales_cost = None
        else:
            sales_date = None
            sales_cost = None

        return CarFullInfo(
            vin=car_fields[0],
            car_model_name=model_fields[1],
            car_model_brand=model_fields[2],
            price=Decimal(car_fields[2]),
            date_start=datetime.fromisoformat(car_fields[3]),
            status=CarStatus(car_fields[4]),
            sales_date=sales_date,
            sales_cost=sales_cost
        )
       
    # Задание 5. Обновление ключевого поля
    def update_vin(self, vin: str, new_vin: str) -> Car:
        car_info = self.__get_data_by_field(CARS, vin)
        if not car_info:
            return None

        car_record, line_number = car_info
        car_fields = car_record.split(';')
        car = Car(
            vin=new_vin,
            model=int(car_fields[1]),
            price=Decimal(car_fields[2]),
            date_start=datetime.fromisoformat(car_fields[3]),
            status=CarStatus(car_fields[4])
        )
        self.__update(CARS, (car.vin, car.model, car.price, car.date_start.isoformat(), car.status), line_number)
        self.__index_build(CARS, new_vin, vin, line_number)
        return car
        
    # Задание 6. Удаление продажи
    def revert_sale(self, sales_number: str) -> Car:
        sales_info = self.__get_data_sec_scan(CMS[SALES], sales_number)
        if not sales_info:
            return None

        sales_fields = sales_info.split(';')
        car_vin = sales_fields[1]

        car_info = self.__get_data_by_field(CARS, car_vin)
        if not car_info:
            return None

        car_record, line_number = car_info
        car_fields = car_record.split(';')
        car = Car(
            vin=car_fields[0],
            model=int(car_fields[1]),
            price=Decimal(car_fields[2]),
            date_start=datetime.fromisoformat(car_fields[3]),
            status=CarStatus.available
        )
        self.__update(CARS, (car.vin, car.model, car.price, car.date_start.isoformat(), car.status), line_number)

        with open(f'{self.root_directory_path}/{CMS[SALES]}', "r") as f:
            lines = f.readlines()
        with open(f'{self.root_directory_path}/{CMS[SALES]}', "w") as f:
            for line in lines:
                if sales_number not in line:
                    f.write(line)

        return car
       
    # Задание 7. Самые продаваемые модели
    def top_models_by_sales(self) -> list[ModelSaleStats]:
        sales_count = {}
        model_prices = {}

        with open(f'{self.root_directory_path}/{CMS[SALES]}', "r") as f:
            for line in f:
                sales_fields = line.strip().split(';')
                car_vin = sales_fields[1]
                car_info = self.__get_data_by_field(CARS, car_vin)
                if car_info:
                    car_record, _ = car_info
                    car_fields = car_record.split(';')
                    model_id = car_fields[1]
                    sales_count[model_id] = sales_count.get(model_id, 0) + 1
                    model_prices[model_id] = model_prices.get(model_id, Decimal(0)) + Decimal(car_fields[2])

        for model_id in model_prices:
            model_prices[model_id] /= sales_count[model_id]

        sorted_models = sorted(
            sales_count.items(),
            key=lambda x: (-x[1], -model_prices[x[0]])
        )

        top_models = sorted_models[:3]

        result = []
        for model_id, count in top_models:
            model_info = self.__get_data_by_field(MODELS, model_id)
            if model_info:
                model_record, _ = model_info
                model_fields = model_record.split(';')
                result.append(ModelSaleStats(
                    car_model_name=model_fields[1],
                    brand=model_fields[2],
                    sales_number=count
                ))
        return result
    
    # Вспомогательные методы
    def __create_record(self, str_len: int, tuple: tuple) -> str:
        result = ''
        for value in tuple:
            result += str(value) + ';'
        return result.ljust(str_len) + '\n'
    
    def __insert_into_file(self, file_name: str, data: str):
        with open(f'{self.root_directory_path}/{file_name}', "a") as f:
            f.write(data)

    def __index_build(self, file_name: str, value: int | str, old_value: int | str = None, line_number: int = None) -> None:
        dict: SortedDict = self.__index_array[file_name]

        if old_value is None and line_number is not None:
            dict.pop(value)
        elif old_value is None:
            dict[value] = len(dict)
        elif old_value is not None and line_number is not None:
            dict.pop(old_value)
            dict[value] = line_number

        with open(f'{self.root_directory_path}/{file_name}_index', "w") as f:
            arr = []
            for i in dict.items():
                str = self.__create_record(self.__extend_index_size, (i[0], i[1]))
                arr.append(str)
            f.writelines(arr)

    def __get_line_from_index(self, value: str | int, index: SortedDict) -> int | None:
        return index[value] if value in index else None
    
    def __get_record_by_line(self, line_number: int, file_name: str) -> str | None:
        with open(f'{self.root_directory_path}/{file_name}', "r") as f:
            f.seek(line_number * (self.__extend_file_size + 1))
            return f.read(self.__extend_file_size)
        
    def __get_data_by_field(self, file_name: str, field: str | int) -> tuple[tuple, int] | None:
        line = self.__get_line_from_index(field, self.__index_array[file_name])
        if line is not None:
            record = self.__get_record_by_line(line, CMS[file_name])
            return (record, line)
        return None
    
    def __get_data_sec_scan(self, file_name: str, search_value: str | int) -> tuple | None:
        with open(f'{self.root_directory_path}/{file_name}', "r") as f:
            for line in f:
                if search_value in line:
                    return line.strip()
        return None
    
    def __insert(self, file_name: str, data: str, index_field: int | str):
        self.__insert_into_file(file_name, self.__create_record(self.__extend_file_size, data))
        self.__index_build(file_name, index_field)

    def __update(self, file_name: str, data: str, line_number: int):
        with open(f'{self.root_directory_path}/{file_name}', "r+") as f:
            f.seek(line_number * (self.__extend_file_size + 1))
            f.write(self.__create_record(self.__extend_file_size, data))