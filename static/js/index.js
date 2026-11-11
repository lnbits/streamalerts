const mapStreamAlerts = obj => {
  obj.date = Quasar.date.formatDate(new Date(obj.time), 'YYYY-MM-DD HH:mm')
  obj.fsat = new Intl.NumberFormat(LOCALE).format(obj.amount)
  obj.redirectURI = ['/streamalerts/api/v1/authenticate/', obj.id].join('')
  obj.authUrl = ['/streamalerts/api/v1/getaccess/', obj.id].join('')
  obj.displayUrl = ['/streamalerts/', obj.state].join('')
  return obj
}

window.app = Vue.createApp({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      servicenames: ['Streamlabs'],
      services: [],
      donations: [],
      walletLinks: [],
      coreOnchainWallets: [],
      loadingOnchainWallets: false,
      servicesTable: {
        columns: [
          {
            name: 'id',
            align: 'left',
            label: 'ID',
            field: 'id'
          },
          {
            name: 'twitchuser',
            align: 'left',
            label: 'Twitch Username',
            field: 'twitchuser'
          },
          {
            name: 'wallet',
            align: 'left',
            label: 'Wallet',
            field: 'wallet'
          },
          {
            name: 'onchain address',
            align: 'left',
            label: 'Onchain Wallet',
            field: 'onchain'
          },
          {
            name: 'servicename',
            align: 'left',
            label: 'Service',
            field: 'servicename'
          },
          {
            name: 'client_id',
            align: 'left',
            label: 'Client ID',
            field: 'client_id'
          },
          {
            name: 'client_secret',
            align: 'left',
            label: 'Client Secret',
            field: 'client_secret'
          },
          {
            name: 'authenticated',
            align: 'left',
            label: 'Authenticated',
            field: 'authenticated'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      donationsTable: {
        columns: [
          {
            name: 'service',
            align: 'left',
            label: 'Service',
            field: 'service'
          },
          {name: 'id', align: 'left', label: 'Charge ID', field: 'id'},
          {name: 'name', align: 'left', label: 'Donor', field: 'name'},
          {
            name: 'message',
            align: 'left',
            label: 'Message',
            field: 'message'
          },
          {name: 'sats', align: 'left', label: 'Sats', field: 'sats'},
          {
            name: 'posted',
            align: 'left',
            label: 'Posted to API',
            field: 'posted'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      serviceDialog: {
        show: false,
        chain: false,
        data: {}
      }
    }
  },
  computed: {
    editingService() {
      return this.services.find(
        service => service.id === this.serviceDialog.data.id
      )
    },
    lightningWalletOptions() {
      const walletIds = this.g.user.wallets
        .filter(wallet => wallet.canReceivePayments)
        .map(wallet => wallet.id)
      return this.g.user.walletOptions.filter(wallet =>
        walletIds.includes(wallet.value)
      )
    },
    onchainWalletOptions() {
      const core = this.coreOnchainWallets.map(wallet => ({
        label: `LNbits: ${wallet.name}${wallet.status === 'ready' ? '' : ' (Not ready)'}`,
        value: `core:${wallet.id}`
      }))
      const watchonly = this.walletLinks.map(wallet => ({
        label: `Watchonly: ${wallet.title || wallet.id}`,
        value: wallet.id
      }))
      return [...core, ...watchonly]
    },
    selectedCoreWallet() {
      const reference = this.serviceDialog.data.onchain
      if (!reference?.startsWith('core:')) return null
      return (
        this.coreOnchainWallets.find(w => w.id === reference.slice(5)) || null
      )
    },
    hasCoreOnchainWallet() {
      return this.g.user.wallets.some(wallet => wallet.walletType === 'onchain')
    },
    onchainSelectionInvalid() {
      if (!this.serviceDialog.chain) return false
      const reference = this.serviceDialog.data.onchain
      if (reference && reference === this.editingService?.onchain) return false
      return (
        !this.onchainWalletOptions.some(option => option.value === reference) ||
        (reference?.startsWith('core:') &&
          this.selectedCoreWallet?.status !== 'ready')
      )
    }
  },
  methods: {
    async getWalletLinks() {
      if (this.loadingOnchainWallets) return
      this.loadingOnchainWallets = true
      this.walletLinks = []
      this.coreOnchainWallets = []
      const inkey = this.g.user.wallets[0].inkey
      try {
        const {
          data: {network}
        } = await LNbits.api.request('GET', '/satspay/api/v1/settings/public')
        const core = LNbits.api
          .request('GET', '/satspay/api/v1/onchain-wallets', inkey)
          .then(({data}) => {
            this.coreOnchainWallets = data.filter(
              wallet => wallet.network === network
            )
          })
          .catch(LNbits.utils.notifyApiError)
        if (this.g.user.extensions.includes('watchonly')) {
          await Promise.all([core, this.getWatchonlyWallets(network, inkey)])
        } else {
          await core
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      } finally {
        this.loadingOnchainWallets = false
      }
    },
    async getWatchonlyWallets(network, inkey) {
      try {
        const {data: config} = await LNbits.api.request(
          'GET',
          '/watchonly/api/v1/config',
          inkey
        )
        if (config.network !== network) {
          this.$q.notify({
            type: 'warning',
            message: `Watchonly must use the SatsPay network (${network}).`
          })
          return
        }
        const {data} = await LNbits.api.request(
          'GET',
          `/watchonly/api/v1/wallet?network=${encodeURIComponent(network)}`,
          inkey
        )
        this.walletLinks = data
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },
    createOnchainWallet() {
      this.g.newWalletType = 'onchain'
    },
    openOnchainWallet(walletId) {
      this.$router.push({path: '/wallet', query: {wal: walletId}})
    },
    openServiceDialog() {
      this.serviceDialog.data = {}
      this.serviceDialog.chain = false
      this.serviceDialog.show = true
    },
    getDonations() {
      LNbits.api
        .request(
          'GET',
          '/streamalerts/api/v1/donations',
          this.g.user.wallets[0].inkey
        )
        .then(response => {
          this.donations = response.data.map(function (obj) {
            return mapStreamAlerts(obj)
          })
        })
    },
    deleteDonation(donationId) {
      const donations = _.findWhere(this.donations, {id: donationId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this donation?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/streamalerts/api/v1/donations/' + donationId,
              _.findWhere(this.g.user.wallets, {id: donations.wallet}).inkey
            )
            .then(response => {
              this.donations = _.reject(this.donations, function (obj) {
                return obj.id == ticketId
              })
            })
            .catch(LNbits.utils.notifyApiError)
        })
    },
    exportdonationsCSV() {
      LNbits.utils.exportCSV(this.donationsTable.columns, this.donations)
    },

    getServices() {
      LNbits.api
        .request(
          'GET',
          '/streamalerts/api/v1/services',
          this.g.user.wallets[0].inkey
        )
        .then(response => {
          this.services = response.data.map(function (obj) {
            return mapStreamAlerts(obj)
          })
        })
    },
    sendServiceData() {
      if (this.onchainSelectionInvalid) return
      const data = {
        ...this.serviceDialog.data,
        onchain: this.serviceDialog.chain
          ? this.serviceDialog.data.onchain
          : null
      }
      const wallet = this.g.user.wallets.find(
        wallet => wallet.id === data.wallet
      )
      return LNbits.api
        .request(
          data.id ? 'PUT' : 'POST',
          '/streamalerts/api/v1/services' + (data.id ? `/${data.id}` : ''),
          wallet.adminkey,
          data
        )
        .then(response => {
          const service = mapStreamAlerts(response.data)
          if (data.id) {
            this.services = this.services.map(row =>
              row.id === data.id ? service : row
            )
          } else {
            this.services.push(service)
          }
          this.serviceDialog.show = false
          this.serviceDialog.data = {}
        })
        .catch(LNbits.utils.notifyApiError)
    },
    updateserviceDialog(serviceId) {
      const {
        id,
        wallet,
        twitchuser,
        servicename,
        client_id,
        client_secret,
        onchain
      } = this.services.find(service => service.id === serviceId)
      this.serviceDialog.data = {
        id,
        wallet,
        twitchuser,
        servicename,
        client_id,
        client_secret,
        onchain
      }
      this.serviceDialog.chain = Boolean(onchain)
      this.serviceDialog.show = true
      if (this.serviceDialog.chain) this.getWalletLinks()
    },
    deleteService(servicesId) {
      const services = _.findWhere(this.services, {id: servicesId})

      LNbits.utils
        .confirmDialog('Are you sure you want to delete this service link?')
        .onOk(() => {
          LNbits.api
            .request(
              'DELETE',
              '/streamalerts/api/v1/services/' + servicesId,
              _.findWhere(this.g.user.wallets, {id: services.wallet}).inkey
            )
            .then(response => {
              this.services = _.reject(this.services, function (obj) {
                return obj.id == servicesId
              })
            })
            .catch(LNbits.utils.notifyApiError)
        })
    },
    exportservicesCSV() {
      LNbits.utils.exportCSV(this.servicesTable.columns, this.services)
    }
  },

  created() {
    if (this.g.user.wallets.length) {
      this.getDonations()
      this.getServices()
    }
  }
})
