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
            label: 'Onchain Address',
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
  methods: {
    getWalletLinks() {
      LNbits.api
        .request(
          'GET',
          '/watchonly/api/v1/wallet',
          this.g.user.wallets[0].inkey
        )
        .then(response => {
          for (i = 0; i < response.data.length; i++) {
            this.walletLinks.push(response.data[i].id)
          }
          return
        })
        .catch(LNbits.utils.notifyApiError)
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
      const wallet = _.findWhere(this.g.user.wallets, {
        id: this.serviceDialog.data.wallet
      })
      const data = this.serviceDialog.data

      this.createService(wallet, data)
    },

    createService(wallet, data) {
      LNbits.api
        .request('POST', '/streamalerts/api/v1/services', wallet.adminkey, data)
        .then(response => {
          this.services.push(mapStreamAlerts(response.data))
          this.serviceDialog.show = false
          this.serviceDialog.data = {}
        })
        .catch(LNbits.utils.notifyApiError)
    },
    updateserviceDialog(serviceId) {
      const link = _.findWhere(this.services, {id: serviceId})
      this.serviceDialog.data.id = link.id
      this.serviceDialog.data.wallet = link.wallet
      this.serviceDialog.data.twitchuser = link.twitchuser
      this.serviceDialog.data.servicename = link.servicename
      this.serviceDialog.data.client_id = link.client_id
      this.serviceDialog.data.client_secret = link.client_secret
      this.serviceDialog.show = true
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
      this.getWalletLinks()
      this.getDonations()
      this.getServices()
    }
  }
})
