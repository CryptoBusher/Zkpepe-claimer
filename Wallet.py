import json
import os

import requests
from web3 import Web3

import config
from data.contract_abi import CONTRACT_ABI

w3 = Web3(Web3.HTTPProvider(config.RPC))
contract = w3.eth.contract(w3.to_checksum_address(config.CONTRACT_ADDRESS), abi=CONTRACT_ABI)


class FailedToSendTxException(Exception):
    pass


class FailedToCheckTxDataException(Exception):
    pass


class FailedToWrapProxyError(Exception):
    pass


class Wallet:
    def __init__(self, private_key: str, number: int, _proxy: str | None = None):
        self.private_key = private_key
        self.number = number
        self.proxy = _proxy

        self.session = self.create_session()
        self.account = self.create_account()
        self.address = self.get_wallet_address()

        self.claimable_amount = 0
        self.proof = None

    def create_account(self):
        account = w3.eth.account.from_key(self.private_key)
        return account

    def get_wallet_address(self):
        return self.account.address

    def create_session(self):
        session = requests.Session()
        if self.proxy:
            session.proxies.update({
                "http": self.proxy
            })

        return session

    def get_claimable_amount(self):
        url = f"https://www.zksyncpepe.com/resources/amounts/{self.address.lower()}.json"
        response = self.session.get(url)

        try:
            json_response = json.loads(response.text)
            return json_response[0]
        except json.decoder.JSONDecodeError:
            return 0

    def get_proof(self):
        url = f"https://www.zksyncpepe.com/resources/proofs/{self.address.lower()}.json"
        response = self.session.get(url)
        json_response = json.loads(response.text)
        return json_response

    def set_env_proxy(self):
        os.environ['HTTP_PROXY'] = self.proxy
        os.environ['HTTPS_PROXY'] = self.proxy

    @staticmethod
    def clear_env_proxy():
        try:
            del os.environ['HTTP_PROXY']
        except KeyError:
            pass
        try:
            del os.environ['HTTPS_PROXY']
        except KeyError:
            pass

    def validate_env_proxy(self):
        url = "https://api.ipify.org?format=json"
        response = requests.get(url)
        json_response = json.loads(response.text)
        wallet_proxy_ip = self.proxy.split("@")[1].split(":")[0]

        if json_response["ip"] != wallet_proxy_ip:
            self.clear_env_proxy()
            raise FailedToWrapProxyError

    def claim(self):
        if self.proxy and not config.USE_PROXY_FOR_HTTP_RQ_ONLY:
            self.set_env_proxy()
            self.validate_env_proxy()

        base_fee = w3.eth.get_block(w3.eth.get_block_number())["baseFeePerGas"]
        max_fee_per_gas = base_fee
        max_priority_fee_per_gas = base_fee

        tx_args = contract.encodeABI("claim", args=(
            self.proof,
            w3.to_wei(self.claimable_amount, "ether")
        ))

        tx_params = {
            'chainId': w3.eth.chain_id,
            "from": self.address,
            "to": config.CONTRACT_ADDRESS,
            "type": "0x2",
            'maxFeePerGas': max_fee_per_gas,
            'maxPriorityFeePerGas': max_priority_fee_per_gas,
            "nonce": w3.eth.get_transaction_count(self.address),
            'data': tx_args,
        }

        tx_params['gas'] = w3.eth.estimate_gas(tx_params)

        sign = self.account.sign_transaction(tx_params)

        try:
            tx_hash = w3.eth.send_raw_transaction(sign.rawTransaction)
        except Exception:
            self.clear_env_proxy()
            raise FailedToSendTxException

        try:
            tx_data = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            if "gasUsed" not in tx_data:
                raise FailedToCheckTxDataException
        except Exception:
            self.clear_env_proxy()
            raise FailedToCheckTxDataException

        self.clear_env_proxy()

