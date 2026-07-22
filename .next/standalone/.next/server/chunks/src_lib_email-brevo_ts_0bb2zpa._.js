module.exports=[42616,e=>{"use strict";let t=process.env.BREVO_API_KEY,o=process.env.EMAIL_FROM_EMAIL||"noreply@flexpay.com",r=process.env.EMAIL_FROM_NAME||"FlexPay";async function a(e){if(!t)return console.error("[Email] ❌ BREVO_API_KEY not configured"),{success:!1,error:"Email service not configured"};try{let a=Array.isArray(e.to)?e.to:[e.to],n={sender:{name:r,email:o},to:a.map(e=>({email:e})),subject:e.subject,htmlContent:e.htmlContent,textContent:e.textContent||e.htmlContent.replace(/<[^>]*>/g,"").replace(/\s+/g," ").trim(),replyTo:e.replyTo?{email:e.replyTo}:void 0,headers:e.headers,tags:["flexpay",...e.tags||[]]};console.log(`[Email] 📧 Sending to ${a.join(", ")}: ${e.subject}`);let i=await fetch("https://api.brevo.com/v3/smtp/email",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json","api-key":t},body:JSON.stringify(n)}),s=await i.json();if(!i.ok)return console.error("[Email] ❌ Brevo API error:",s),{success:!1,error:s.message||`API Error: ${i.status}`};return console.log(`[Email] ✅ Sent successfully! Message ID: ${s.messageId}`),{success:!0,messageId:s.messageId}}catch(t){let e=t instanceof Error?t.message:"Unknown error";return console.error("[Email] ❌ Send error:",e),{success:!1,error:e}}}async function n(e){let{to:t,otpCode:o,userName:r,expiryMinutes:n=10}=e;return a({to:t,subject:`Your FlexPay Verification Code: ${o}`,htmlContent:`
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; padding:20px;">
    
    <!-- Header -->
    <tr>
      <td style="background:linear-gradient(135deg,#f97316,#f59e0b); padding:30px; border-radius:16px 16px 0 0; text-align:center;">
        <h1 style="margin:0; color:white; font-size:28px;">🚀 FlexPay</h1>
        <p style="margin:8px 0 0; color:rgba(255,255,255,0.9);">Verify your email address</p>
      </td>
    </tr>
    
    <!-- Content -->
    <tr>
      <td style="background:white; padding:40px 30px; border:1px solid #e4e4e7;">
        
        <p style="margin:0 0 16px; color:#3f3f46; font-size:16px;">
          Hi ${r||"there"}, 👋
        </p>
        
        <p style="margin:0 0 24px; color:#52525b; font-size:15px; line-height:1.6;">
          Use the verification code below to complete your setup. This code will expire in <strong>${n} minutes</strong>.
        </p>
        
        <!-- OTP Code -->
        <div style="background:#fafafa; border:2px dashed #f97316; border-radius:12px; padding:24px; margin:24px 0; text-align:center;">
          <p style="margin:0 0 8px; color:#71717a; font-size:13px; text-transform:uppercase; letter-spacing:1px;">Your Verification Code</p>
          <p style="margin:0; font-size:36px; font-weight:700; letter-spacing:8px; color:#f97316; font-family:'Courier New',monospace;">
            ${o}
          </p>
        </div>
        
        <p style="margin:24px 0 0; color:#a1a1aa; font-size:13px; text-align:center;">
          ⏰ This code expires in ${n} minutes<br>
          🔒 Never share this code with anyone
        </p>
        
      </td>
    </tr>
    
    <!-- Footer -->
    <tr>
      <td style="background:#18181b; padding:24px; border-radius:0 0 16px 16px; text-align:center;">
        <p style="margin:0 0 8px; color:#a1a1aa; font-size:13px;">
          Need help? <a href="mailto:support@flexpay.com" style="color:#f97316;text-decoration:none;">Contact Support</a>
        </p>
        <p style="margin:0; color:#71717a; font-size:12px;">
          \xa9 2026 FlexPay. All rights reserved.
        </p>
      </td>
    </tr>
    
  </table>
  
</body>
</html>`,tags:["otp-verification"]})}async function i(e){let{to:t,userName:o,amount:r,currency:n="INR",planName:i,orderId:s,status:l}=e,p="completed"===l,d=p?`Payment Confirmed ✅ ₹${r} for ${i}`:`Payment Update: ${i}`,c=p?"#10b981":"#f59e0b";return a({to:t,subject:d,htmlContent:`
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
</head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; padding:20px;">
    
    <tr>
      <td style="background:${c}; padding:30px; border-radius:16px 16px 0 0; text-align:center;">
        <h1 style="margin:0; color:white; font-size:28px;">${p?"✅":"⏳"} Payment ${p?"Confirmed":"Update"}</h1>
        <p style="margin:8px 0 0; color:rgba(255,255,255,0.9);">
          ${p?"Thank you for your payment!":"Your payment is being processed"}
        </p>
      </td>
    </tr>
    
    <tr>
      <td style="background:white; padding:40px 30px; border:1px solid #e4e4e7;">
        
        <p style="margin:0 0 24px; color:#52525b;">
          Hi${o?`, ${o}`:""},
        </p>
        
        <!-- Payment Details -->
        <div style="background:#fafafa; border-radius:12px; padding:24px; margin:20px 0;">
          
          <table style="width:100%; border-collapse:collapse;">
            <tr>
              <td style="padding:12px 0; color:#71717a; font-size:14px;">Plan</td>
              <td style="padding:12px 0; text-align:right; color:#18181b; font-weight:600;">${i}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Amount</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right; color:#18181b; font-weight:700; font-size:18px;">₹${r.toLocaleString()}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Order ID</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right; color:#18181b; font-family:monospace; font-size:13px;">${s}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Status</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right;">
                <span style="display:inline-block; background:${c}20; color:${c}; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600;">
                  ${l.charAt(0).toUpperCase()+l.slice(1)}
                </span>
              </td>
            </tr>
          </table>
          
        </div>
        
        ${p?`
        <p style="margin:24px 0 0; color:#52525b; font-size:14px; text-align:center;">
          A detailed receipt will be available in your dashboard.
        </p>
        `:""}
        
      </td>
    </tr>
    
    <tr>
      <td style="background:#18181b; padding:24px; border-radius:0 0 16px 16px; text-align:center;">
        <p style="margin:0; color:#71717a; font-size:12px;">
          Questions? <a href="mailto:billing@flexpay.com" style="color:#f97316;text-decoration:none;">Contact Billing</a>
        </p>
      </td>
    </tr>
    
  </table>
</body>
</html>`,tags:["payment",`payment-${l}`,i.toLowerCase()]})}e.s(["sendOtpEmail",0,n,"sendPaymentReceipt",0,i])}];

//# sourceMappingURL=src_lib_email-brevo_ts_0bb2zpa._.js.map