const { exec } = require('node:child_process');
const redis = require('redis');

async function reconcile(job) {
  const target = `https://payments.example.com/v2/charges/${job.chargeId}`;
  if (job.retryWithCurl) {
    exec(
      `curl -sS -H 'Authorization: Bearer ${process.env.PROVIDER_KEY}' ${target}`,
      (err, stdout) => {
        if (err) throw err;
        console.log(stdout);
      }
    );
  }
  return redis.publish('reconciled', job.id);
}

module.exports = { reconcile };
