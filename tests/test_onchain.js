const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

function page(request, extensions = ['watchonly']) {
  const context = {
    window: {},
    windowMixin: {},
    Vue: {createApp: component => component},
    Quasar: {date: {formatDate: () => ''}},
    LOCALE: 'en',
    _: {findWhere: (items, {id}) => items.find(item => item.id === id)},
    LNbits: {api: {request}, utils: {notifyApiError: () => {}}}
  }
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, '../static/js/index.js'), 'utf8'),
    context
  )
  const component = context.window.app
  const state = {
    ...component.data(),
    ...component.methods,
    g: {
      user: {
        extensions,
        wallets: [{id: 'merchant', adminkey: 'admin', inkey: 'invoice'}]
      }
    }
  }
  for (const [name, get] of Object.entries(component.computed)) {
    Object.defineProperty(state, name, {get: () => get.call(state)})
  }
  return state
}

test('discovery filters by SatsPay network and tolerates Watchonly failure', async () => {
  const calls = []
  const state = page(async (method, url, key) => {
    calls.push([url, key])
    if (url.endsWith('/settings/public')) return {data: {network: 'Mainnet'}}
    if (url.endsWith('/onchain-wallets'))
      return {
        data: [
          {id: 'main', name: 'Main', status: 'ready', network: 'Mainnet'},
          {id: 'test', name: 'Test', status: 'ready', network: 'Testnet4'}
        ]
      }
    throw new Error('Watchonly unavailable')
  })

  await state.getWalletLinks()
  assert.deepEqual(
    Array.from(state.onchainWalletOptions, option => option.value),
    ['core:main']
  )
  assert.deepEqual(calls.slice(1), [
    ['/satspay/api/v1/onchain-wallets', 'invoice'],
    ['/watchonly/api/v1/config', 'invoice']
  ])
})

test('editing the onchain choice keeps the existing service and does not submit its token', async () => {
  const requests = []
  const state = page(async (method, url, key, data) => {
    requests.push({method, url, key, data})
    return {data}
  }, [])
  state.services = [
    {
      id: 'service',
      state: 'public-link',
      wallet: 'merchant',
      token: 'token',
      client_id: 'client',
      client_secret: 'secret',
      servicename: 'Streamlabs',
      twitchuser: 'streamer',
      onchain: null
    }
  ]
  state.updateserviceDialog('service')
  state.serviceDialog.chain = true
  state.serviceDialog.data.onchain = 'core:main'
  state.coreOnchainWallets = [{id: 'main', status: 'ready'}]
  await state.sendServiceData()

  assert.equal(requests[0].method, 'PUT')
  assert.equal(requests[0].url, '/streamalerts/api/v1/services/service')
  assert.equal(requests[0].key, 'admin')
  assert.equal(requests[0].data.onchain, 'core:main')
  assert.equal(requests[0].data.token, undefined)
  assert.equal(state.services.length, 1)
})
