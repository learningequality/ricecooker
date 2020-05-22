from ricecooker.chefs import BaseChef

if __name__ == '__main__':
    """
    Entry point used when starting a sushichef using the ricecooker as a module:
        python -m ricecooker uploadchannel --token=<studio-access-token>
    """
    chef = BaseChef(compatibility_mode=True)
    chef.main()
