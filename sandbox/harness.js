// Runs solve on each case and prints the outputs. Exit 2 means a limit was hit.
'use strict'
const vm = require('node:vm')

let raw = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', chunk => { raw += chunk })
process.stdin.on('end', () => {
  let msg
  try { msg = JSON.parse(raw) } catch { process.exit(1) }
  const context = vm.createContext(Object.create(null), { codeGeneration: { strings: false, wasm: false } })
  let solve
  try {
    vm.runInContext(`${msg.source}\n;globalThis.__solve = typeof solve === 'function' ? solve : undefined`, context,
      { filename: 'solution.js', timeout: 2500 })
    solve = context.__solve
  } catch (err) {
    process.exit(err && err.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT' ? 2 : 1)
  }
  if (typeof solve !== 'function') process.exit(1)
  const out = []
  for (const args of msg.cases) {
    let value = null
    try {
      context.__args = JSON.parse(JSON.stringify(args))
      value = vm.runInContext('__solve(...__args)', context, { timeout: 2500 })
    } catch (err) {
      // Errors thrown inside the context belong to its realm: compare by name, not instanceof.
      if (err && (err.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT' || err.name === 'RangeError')) process.exit(2)
      value = null
    }
    out.push(Number.isSafeInteger(value) ? value : null)
  }
  process.stdout.write(JSON.stringify(out))
})
