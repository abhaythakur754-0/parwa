// Test FlexPay Math - UPDATED: Only PARWA High has double-charge

const BASE_DAILY_AMOUNT = 100;
const DOUBLE_CHARGE_INTERVAL = 3;
const COLLECTION_WINDOW_DAYS = 30;

function calculateSchedule(totalAmount, tier) {
  const schedule = [];
  let remainingAmount = totalAmount;
  let day = 1;

  // ONLY high tier uses double-charge
  const useDoubleCharge = tier === 'high';

  while (remainingAmount > 0 && day <= COLLECTION_WINDOW_DAYS) {
    const isDoubleChargeDay = useDoubleCharge && (day % DOUBLE_CHARGE_INTERVAL === 0);
    
    let primaryAmount = Math.min(BASE_DAILY_AMOUNT, remainingAmount);
    let secondaryAmount = 0;
    
    if (isDoubleChargeDay && remainingAmount > BASE_DAILY_AMOUNT) {
      secondaryAmount = Math.min(BASE_DAILY_AMOUNT, remainingAmount - primaryAmount);
      if (remainingAmount < BASE_DAILY_AMOUNT * 2) {
        const halfRemaining = Math.ceil(remainingAmount / 2);
        primaryAmount = Math.min(halfRemaining, remainingAmount);
        secondaryAmount = remainingAmount - primaryAmount;
      }
    }

    const totalForDay = primaryAmount + secondaryAmount;
    schedule.push({
      day,
      amount: primaryAmount,
      ...(secondaryAmount > 0 ? { secondaryAmount } : {}),
      totalForDay,
      isDoubleChargeDay: isDoubleChargeDay && secondaryAmount > 0,
    });

    remainingAmount -= totalForDay;
    day++;
  }

  return schedule;
}

console.log('═'.repeat(60));
console.log('FLEXPAY MATH - UPDATED (Double charge ONLY for High tier)');
console.log('═'.repeat(60));

// Test Mini PARWA ($999)
const miniSchedule = calculateSchedule(999, 'mini');
const miniTotal = miniSchedule.reduce((sum, s) => sum + s.totalForDay, 0);
const miniDoubleDays = miniSchedule.filter(s => s.isDoubleChargeDay).length;

console.log('\n📦 MINI PARWA - $999/month');
console.log('─'.repeat(40));
console.log('Days to collect:', miniSchedule.length);
console.log('Daily amount: $100 (NO double charge)');
console.log('Double-charge days:', miniDoubleDays, '(should be 0)');
console.log('TOTAL: $' + miniTotal, miniTotal === 999 ? '✅' : '❌');

// Show breakdown
console.log('\nBreakdown:');
miniSchedule.forEach(s => {
  console.log(`  Day ${s.day}: $${s.totalForDay}`);
});

// Test PARWA ($2,499)
const parwaSchedule = calculateSchedule(2499, 'parwa');
const parwaTotal = parwaSchedule.reduce((sum, s) => sum + s.totalForDay, 0);
const parwaDoubleDays = parwaSchedule.filter(s => s.isDoubleChargeDay).length;

console.log('\n\n📦 PARWA - $2,499/month');
console.log('─'.repeat(40));
console.log('Days to collect:', parwaSchedule.length);
console.log('Daily amount: $100 (NO double charge)');
console.log('Double-charge days:', parwaDoubleDays, '(should be 0)');
console.log('TOTAL: $' + parwaTotal, parwaTotal === 2499 ? '✅' : '❌');

// Test PARWA High ($3,999)
const highSchedule = calculateSchedule(3999, 'high');
const highTotal = highSchedule.reduce((sum, s) => sum + s.totalForDay, 0);
const highDoubleDays = highSchedule.filter(s => s.isDoubleChargeDay).length;

console.log('\n\n📦 PARWA HIGH - $3,999/month');
console.log('─'.repeat(40));
console.log('Days to collect:', highSchedule.length);
console.log('Normal days ($100):', highSchedule.length - highDoubleDays);
console.log('Double-charge days ($200):', highDoubleDays, '(should be 10)');
console.log('TOTAL: $' + highTotal, highTotal === 3999 ? '✅' : '❌');

// Summary
console.log('\n' + '═'.repeat(60));
console.log('SUMMARY');
console.log('═'.repeat(60));
console.log('Mini PARWA:   $100/day ×', miniSchedule.length, 'days = $' + miniTotal, '| Double charges:', miniDoubleDays);
console.log('PARWA:        $100/day ×', parwaSchedule.length, 'days = $' + parwaTotal, '| Double charges:', parwaDoubleDays);
console.log('PARWA High:   Mixed   ×', highSchedule.length, 'days = $' + highTotal, '| Double charges:', highDoubleDays);
