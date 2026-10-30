from pydantic import BaseModel
from fastapi import FastAPI, HTTPException,Depends
import requests
import logging
import json
import os
from datetime import datetime
import shutil
import bcrypt
import uuid
import random
from sqlalchemy import Column, String, Integer, Float, ForeignKey, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv




# lOG_DR="var/log"
# logger=logging.getLogger(__name__)
# os.makedirs(lOG_DR, exist_ok=True)
# logger.setLevel(logging.INFO)

# formatter=logging.Formatter(
#     "%(asctime)s | %(levelname)s | %(message)s"
# )
# console_log=logging.StreamHandler()
# console_log.setFormatter(formatter)
# log_file=os.path.join(lOG_DR,"blockchain.log")
# file_handler=logging.FileHandler(log_file)
# file_handler.setFormatter(formatter)
# logger.addHandler(console_log)
# logger.addHandler(file_handler)
# logger.info("Server is starting...")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
DB_FILE = os.path.join(BASE_DIR, os.getenv("DB_FILE"))
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

session_local = sessionmaker(bind=engine)
base = declarative_base()


class UserModel(base):
    __tablename__ = "users"
    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    balance = Column(Float, default=0)
    wallets = relationship("WalletModel", cascade="all, delete-orphan", order_by="WalletModel.id")


class WalletModel(base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, ForeignKey("users.username"), nullable=False)
    symbol = Column(String, nullable=False)
    address = Column(String, unique=True, nullable=False)
    balance = Column(Float, default=0)
    transactions = relationship("TransactionModel", cascade="all, delete-orphan", order_by="TransactionModel.id")


class TransactionModel(base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(String)
    details = Column(JSON)


base.metadata.create_all(engine)

app= FastAPI()

BACKUP_DR = os.path.join(BASE_DIR, "backup")
SYMBOL={
    "sol":"Solana",
    "btc":"bitcoin",
    "usd": "usd"

}

API_ADDRESS=os.getenv("API_ADDRESS")

 

os.makedirs(BACKUP_DR, exist_ok=True)

def load_file():
    data = {}
    with session_local() as session:
        for user in session.query(UserModel).all():
            data[user.username] = {
                "username": user.username,
                "wallets": [
                    {
                        "balance": wallet.balance,
                        "symbol": wallet.symbol,
                        "address": wallet.address,
                        "transaction": [t.details for t in wallet.transactions],
                    }
                    for wallet in user.wallets
                ],
                "balance": user.balance,
                "password": user.password,
            }
    return data

def save_file(data):
    with session_local() as session, session.begin():
        session.query(TransactionModel).delete()
        session.query(WalletModel).delete()
        session.query(UserModel).delete()
        for account in data.values():
            user = UserModel(
                username=account["username"],
                password=account["password"],
                balance=account["balance"],
            )
            for wallet in account["wallets"]:
                user.wallets.append(WalletModel(
                    symbol=wallet["symbol"],
                    address=wallet["address"],
                    balance=wallet["balance"],
                    transactions=[
                        TransactionModel(
                            type=t["type"],
                            amount=t["amount"],
                            timestamp=t.get("timestamp"),
                            details=t,
                        )
                        for t in wallet["transaction"]
                    ],
                ))
            session.add(user)

class Banksystem:
    def __init__(self):
        self.accounts = load_file()
        self.operation_count = 0 

    def save(self):
        save_file(self.accounts)
        self.operation_count += 1
        if self.operation_count >= 5: 
            self.backup()
            self.operation_count = 0

 
    def backup(self):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") 
        backup_file = os.path.join(BACKUP_DR, f"backup_{timestamp}.db")
        try:
            shutil.copy(DB_FILE, backup_file)
            print(f"Backup successful to {backup_file}")
            logger.INFO("Back up seuccesful")
        except Exception as e:
            print(f"Backup failed: {e}")
            # logger.ERROR(f"backuo faild : {e}")
            

    def hash_password(self, password: str):
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode(), salt)
        return hashed_password.decode()
        logger.INFO("hashed password succesful")

   
    def deposit(self, username: str, amount: float, wallet_name: str):
        if username not in self.accounts:
            raise ValueError("User not found")
        if amount <= 0:
            raise ValueError("Amount must be positive")

    
        wallet_found = False
        for wallet in self.accounts[username]["wallets"]:
            if wallet["symbol"] == wallet_name:
                wallet["balance"] += amount
                wallet["transaction"].append({"type": "deposit", "amount": amount, "timestamp": datetime.now().isoformat()})
                self.accounts[username]["balance"] += amount 
                wallet_found = True
                break 
        if not wallet_found:
            raise ValueError(f"You don't have any wallet with name: {wallet_name}")

        self.save()


    def withdraw(self, username: str, amount: float,wallet_name:str):
        if username not in self.accounts:
            raise ValueError("User not found")
        if amount <= 0:
             raise ValueError("Amount must be positive")

        if self.accounts[username]["balance"]<amount:
            raise ValueError("Insufficient balance")

        
        wallet_found = False
        for i in self.accounts[username]["wallets"]:
             if i["symbol"] == wallet_name:
                i["balance"] -= amount
                i["transaction"].append({"type": "withdraw", "amount": amount, "timestamp": datetime.now().isoformat()})
                self.accounts[username]["balance"] -= amount 
                wallet_found = True
        if not wallet_found:
            raise ValueError(f"You don't have any wallet with name: {wallet_name}")

        self.save()


    def transfer(self,sender_username:str,reciever_username:str,amount:float,wallet_from:str,wallet_to:str):
        if sender_username  not in self.accounts:
            print(sender_username,reciever_username)
            raise ValueError(f"{sender_username} not found")
        if reciever_username  not in self.accounts:
            raise ValueError(f"{reciever_username} not found")
        

        # field_check=[
        #         (sender_username,"sender_username"),
        #         (reciever_username,"riciever_username")
        #         ,(amount,"amount"),
        #         (wallet_from,"wallet_from"),
        #         (wallet_to,"wallet_to")
        # ]
            
        # for field,massage in field_check:
        #         if  not field:
        #             error.append(massage)

        # if len(error)>0:
        #     return jsonify({f"{error}is/are not here"})
        if amount<=0:
            raise ValueError("amount must be positive")

        if self.accounts[sender_username]["balance"]<amount:
            raise ValueError("Insufficient balance")

        if wallet_from!=wallet_to:
            raise ValueError("mismatch symbol")


       


            
        else:
            
            wallet_found = False
            for i in self.accounts[sender_username]["wallets"]:
                if i["symbol"] == wallet_from:
                    i["balance"] -= amount
                    i["transaction"].append({"type": "transfer-out", "amount": amount, "timestamp": datetime.now().isoformat()})
                    self.accounts[sender_username]["balance"] -= amount 
                    wallet_found=True
            
            if not wallet_found:
                raise ValueError("sender_username wallet not found")
                    

            wallet2_found = False
            for i in self.accounts[reciever_username]["wallets"]:
                if i["symbol"] == wallet_from:
                    i["balance"] += amount
                    i["transaction"].append({"type": "transfer-in", "amount": amount, "timestamp": datetime.now().isoformat()})
                    self.accounts[reciever_username]["balance"] += amount 
                    wallet2_found=True

                  
            if not wallet2_found:
                raise ValueError("reciever_username wallet not found")
                    

            self.save()
                    

    def create_user(self, username:str, password:str):
        if username in self.accounts:
            raise ValueError("user already exists")

        # print(username)
        hashed = self.hash_password(password)
        self.accounts[username] = {
            "username": username,
            "wallets":[],
            "balance":0,
            "password": hashed,
        }
        self.save()
    def create_wallets(self,username:str,wallet_name:str):
        if username not in self.accounts:
            return("username not found")

        for i in self.accounts[username]["wallets"]:
            if i["symbol"]==wallet_name:
                raise ValueError("symbol already exist")


        
        address_walllet=str(uuid.uuid4())
        
        wallets={
               "balance":0,
            "symbol":wallet_name,
            "address":address_walllet,
            "transaction":[]
        }
        
        self.accounts[username]["wallets"].append(wallets)
        self.save()

    def login_account(self,username:str,password:str):
        account_data=None
        for data in self.accounts.values():
            if data["username"]==username:
                account_data=data
                print(account_data)
                break
        

        if account_data is None:
            raise ValueError("user not found")

        stored_hash = account_data["password"].encode()

        if not bcrypt.checkpw(password.encode(), stored_hash):
            raise ValueError("password is wrong")


    def get_coin(self,symbol_from,symbol_to,amount,username):
        try:
            if symbol_to not in SYMBOL or symbol_from not in SYMBOL:
                raise ValueError("symbol_to or symbol_from not in symbols")

            symbol_from=symbol_from.lower()
            symbol_to=symbol_to.lower()

        



            coin=SYMBOL[symbol_to]
            params = {
                "ids": coin,
                "vs_currencies": symbol_from.lower()
            }


            response=requests.get(API_ADDRESS,params=params)

            data=response.json()
            
            price = data[coin][symbol_from.lower()]

            result = amount * price

            return {
                "from": symbol_from,
                "to": symbol_to,
                "amount": amount,
                "price": price,
                "result": result
            }
            self.save()


        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )



    
    def show_coin(self, username, symbol_from, symbol_to, amount):
        try:


            symbol_from = symbol_from.lower()
            print(symbol_from)
            print(symbol_to)
            print(username)
            symbol_to = symbol_to.lower()
            

            if username not in self.accounts:
                raise ValueError("User not found")

            if symbol_to not in SYMBOL:
                raise ValueError("symbol_to not supported")

            from_wallet = None
            for wallet in self.accounts[username]["wallets"]:
                if wallet["symbol"] == symbol_from:
                    from_wallet = wallet
                    break

            if from_wallet is None:
                raise ValueError(f"{symbol_from} wallet not found")

            if from_wallet["balance"] < amount:
                raise ValueError("Insufficient balance")

           
            to_wallet = None
            for wallet in self.accounts[username]["wallets"]:
                if wallet["symbol"] == symbol_to:
                    to_wallet = wallet
                    break

            if to_wallet is None:
                raise ValueError(f"{symbol_to} wallet not found")

    
            coin = SYMBOL[symbol_to]

            params = {
                "ids": coin,
                "vs_currencies": symbol_from
            }

            response = requests.get(
                API_ADDRESS,
                params=params,
                timeout=5
            )

            response.raise_for_status()

            data = response.json()
            print(data)

            price = data[coin][symbol_from]
            print(price)

            result = round(amount / price, 8)

            from_wallet["balance"] -= amount

        
            to_wallet["balance"] += result

            transaction = {
                "type": "convert",
                "from": symbol_from,
                "to": symbol_to,
                "amount": amount,
                "price": price,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }

            from_wallet["transaction"].append(transaction)
            to_wallet["transaction"].append(transaction)

            self.save()

            return {
                "from": symbol_from,
                "to": symbol_to,
                "amount": amount,
                "price": f"{price} {symbol_from.upper()}",
                "result": result
            }

        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        except requests.exceptions.ConnectionError:
            raise HTTPException(
                status_code=503,
                detail="Internet connection error"
            )

        except requests.exceptions.Timeout:
            raise HTTPException(
                status_code=504,
                detail="Request timeout"
            )

            



bank = Banksystem()

class Usercreate(BaseModel):
    username: str
    password: str



class Transaction(BaseModel): 
    username: str
    amount: float
    wallet_name:str

class transfer_action(BaseModel):
    sender_username:str
    reciever_username:str
    amount:float
    wallet_from:str
    wallet_to:str

class Walletcreate(BaseModel):
    username: str
    wallet_name:str

class Convert(BaseModel):
    symbol_from:str
    symbol_to:str
    amount:int
    username:str
    

class Response_action(BaseModel):
    message: str 
    status: bool
    result: str | None


class response(BaseModel):
    massage: str 
    status: bool

class login(BaseModel):
    username:str
    password:str

@app.post("/login",response_model=response)
def login_route(user:login):
    try:
        a=bank.login_account(user.username,user.password)
        print(a)
        return{"massage":"login succesful","status":True}

    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e))
@app.post("/register",response_model=response)
def register(user: Usercreate):
    try:
        bank.create_user(user.username, user.password)

        return {
            "massage": "User created successfully",
            "status":True
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/create/wallet")
def wallet(user:Walletcreate):
    try:
        bank.create_wallets(user.username,user.wallet_name)
        print(user.wallet_name)
        return{"massage":f"{user.wallet_name} created"}
 
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/deposit", response_model=Response_action)
def deposit(data: Transaction): 
    try:
       
        if data.username not in bank.accounts:
             raise ValueError("User not found")
             
        bank.deposit(data.username, data.amount,data.wallet_name)
        # new_balance = bank.accounts[data.username]["wallets"]["balance"]
        return {
            "message": "Deposit successful",
            "status": True,
            "result": f"New balance for {data.username}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/withdraw", response_model=Response_action)
def withdraw(data: Transaction):
    try:
        bank.withdraw(data.username, data.amount,data.wallet_name)
        new_balance = bank.accounts[data.username]["balance"]
        return {
            "message": "Withdraw successful",
            "status": True,
            "result": f"New balance for {data.username}:{new_balance}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/wallet/{username}")
def get_wallet(username):
    if username not in bank.accounts:
        raise HTTPException(status_code=400, detail="User not found")
    
    show_wallet=bank.accounts[username]["wallets"]
    return(show_wallet)

@app.post("/transfer",response_model=Response_action)
def transfer(data:transfer_action):
    try:
        bank.transfer(data.sender_username,data.reciever_username,data.amount,data.wallet_from,data.wallet_to)
     

        return {
            "message": "transfer successful",
            "status": True,
            "result":f"transfer from {data.sender_username} to {data.reciever_username}"
        
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/convert")
def show_convert(data:Convert):
   result=bank.show_coin(data.username,data.symbol_from,data.symbol_to,data.amount)
   return(result)


@app.post("/show/convert")
def convert(data:Convert):
    result=bank.get_coin(data.symbol_from,data.symbol_to,data.amount)

    return(result)
    

        


app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "static"), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST"), port=int(os.getenv("PORT")))
