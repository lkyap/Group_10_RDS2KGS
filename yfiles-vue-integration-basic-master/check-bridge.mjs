import('@yfiles/yfiles/view-layout-bridge.js').then(m => {
  console.log('bridge exports', Object.keys(m).length)
}).catch(err => {
  console.error(err)
  process.exit(1)
})
