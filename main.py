from time import sleep
import random
from sys import stderr

from pyfiglet import Figlet
from loguru import logger

import config
from Wallet import Wallet, FailedToSendTxException, FailedToCheckTxDataException, FailedToWrapProxyError

logger.remove()
logger.add(stderr, format="<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <white>{message}</white>")


f = Figlet(font='5lineoblique')
print(f.renderText('Busher'))
print('Telegram channel: @CryptoKiddiesClub')
print('Telegram chat: @CryptoKiddiesChat')
print('Twitter: @CryptoBusher\n')


def fetch_sleep():
    delay = random.uniform(config.MIN_FETCH_DELAY_SEC, config.MAX_FETCH_DELAY_SEC)
    sleep(delay)


def claim_sleep():
    delay = random.uniform(config.MIN_CLAIM_DELAY_SEC, config.MAX_CLAIM_DELAY_SEC)
    logger.info(f"Sleeping {delay} seconds")
    sleep(delay)


def record_fail(_wallet: Wallet, reason: str):
    with open(f"fails/{reason}_pk.txt", "a") as f:
        f.write(f"{_wallet.private_key}\n")
    with open(f"fails/{reason}_proxies.txt", "a") as f:
        f.write(f"{_wallet.proxy}\n")


if __name__ == "__main__":
    with open("private_keys.txt", "r") as file:
        private_keys = [line.strip() for line in file]

    with open("proxies.txt", "r") as file:
        proxies = [line.strip() for line in file]

    wallets = []
    for i, key in enumerate(private_keys):
        try:
            proxy = proxies[i]
        except IndexError:
            proxy = None
        wallet_number = i + 1
        wallets.append(Wallet(key, wallet_number, proxy))

    for wallet in wallets:
        wallet.claimable_amount = wallet.get_claimable_amount()
        if wallet.claimable_amount == 0:
            logger.info(f"Wallet {wallet.address} ({wallet.number}) - not eligible, skipping")
        else:
            logger.success(f"Wallet {wallet.address} ({wallet.number}) - {wallet.claimable_amount} tokens to claim")

        fetch_sleep()

    wallets = [w for w in wallets if w.claimable_amount > 0]

    for wallet in wallets:
        for i in range(3):
            try:
                wallet.proof = wallet.get_proof()
                logger.success(f"Wallet {wallet.address} ({wallet.number}) - fetched proof")
                fetch_sleep()
                break
            except:
                fetch_sleep()

        if not wallet.proof:
            logger.error(f"Wallet {wallet.address} ({wallet.number}) - failed to get proof, skipping")
            with open("fails/failed_proof_pk.txt", "a") as file:
                file.write(f"{wallet.private_key}\n")
            with open("fails/failed_proof_proxies.txt", "a") as file:
                file.write(f"{wallet.proxy}\n")

    wallets = [w for w in wallets if w.proof]

    if config.SHUFFLE_WALLETS:
        random.shuffle(wallets)

    for wallet in wallets:
        try:
            wallet.claim()
            logger.success(f"Wallet {wallet.address} ({wallet.number}) - claimed tokens")
        except FailedToSendTxException:
            logger.error(f"Wallet {wallet.address} ({wallet.number}) - failed to send tx")
            record_fail(wallet, "failed_claim")
        except FailedToCheckTxDataException:
            logger.error(f"Wallet {wallet.address} ({wallet.number}) - cannot check tx results")
            record_fail(wallet, "failed_check_result")
        except FailedToWrapProxyError:
            logger.error(f"Wallet {wallet.address} ({wallet.number}) - failed set env proxy, skipping")
            record_fail(wallet, "failed_set_env_proxy")
        except Exception as e:
            logger.error(f"Wallet {wallet.address} ({wallet.number}) - unexpected error: {e}")
            record_fail(wallet, "unexpected_err")
        finally:
            claim_sleep()
