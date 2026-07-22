module.exports=[93695,(e,t,r)=>{t.exports=e.x("next/dist/shared/lib/no-fallback-error.external.js",()=>require("next/dist/shared/lib/no-fallback-error.external.js"))},18622,(e,t,r)=>{t.exports=e.x("next/dist/compiled/next-server/app-page-turbo.runtime.prod.js",()=>require("next/dist/compiled/next-server/app-page-turbo.runtime.prod.js"))},56704,(e,t,r)=>{t.exports=e.x("next/dist/server/app-render/work-async-storage.external.js",()=>require("next/dist/server/app-render/work-async-storage.external.js"))},32319,(e,t,r)=>{t.exports=e.x("next/dist/server/app-render/work-unit-async-storage.external.js",()=>require("next/dist/server/app-render/work-unit-async-storage.external.js"))},24725,(e,t,r)=>{t.exports=e.x("next/dist/server/app-render/after-task-async-storage.external.js",()=>require("next/dist/server/app-render/after-task-async-storage.external.js"))},70406,(e,t,r)=>{t.exports=e.x("next/dist/compiled/@opentelemetry/api",()=>require("next/dist/compiled/@opentelemetry/api"))},42616,e=>{"use strict";let t=process.env.BREVO_API_KEY,r=process.env.EMAIL_FROM_EMAIL||"noreply@flexpay.com",a=process.env.EMAIL_FROM_NAME||"FlexPay";async function n(e){if(!t)return console.error("[Email] ❌ BREVO_API_KEY not configured"),{success:!1,error:"Email service not configured"};try{let n=Array.isArray(e.to)?e.to:[e.to],o={sender:{name:a,email:r},to:n.map(e=>({email:e})),subject:e.subject,htmlContent:e.htmlContent,textContent:e.textContent||e.htmlContent.replace(/<[^>]*>/g,"").replace(/\s+/g," ").trim(),replyTo:e.replyTo?{email:e.replyTo}:void 0,headers:e.headers,tags:["flexpay",...e.tags||[]]};console.log(`[Email] 📧 Sending to ${n.join(", ")}: ${e.subject}`);let s=await fetch("https://api.brevo.com/v3/smtp/email",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json","api-key":t},body:JSON.stringify(o)}),i=await s.json();if(!s.ok)return console.error("[Email] ❌ Brevo API error:",i),{success:!1,error:i.message||`API Error: ${s.status}`};return console.log(`[Email] ✅ Sent successfully! Message ID: ${i.messageId}`),{success:!0,messageId:i.messageId}}catch(t){let e=t instanceof Error?t.message:"Unknown error";return console.error("[Email] ❌ Send error:",e),{success:!1,error:e}}}async function o(e){let{to:t,otpCode:r,userName:a,expiryMinutes:o=10}=e;return n({to:t,subject:`Your FlexPay Verification Code: ${r}`,htmlContent:`
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
          Hi ${a||"there"}, 👋
        </p>
        
        <p style="margin:0 0 24px; color:#52525b; font-size:15px; line-height:1.6;">
          Use the verification code below to complete your setup. This code will expire in <strong>${o} minutes</strong>.
        </p>
        
        <!-- OTP Code -->
        <div style="background:#fafafa; border:2px dashed #f97316; border-radius:12px; padding:24px; margin:24px 0; text-align:center;">
          <p style="margin:0 0 8px; color:#71717a; font-size:13px; text-transform:uppercase; letter-spacing:1px;">Your Verification Code</p>
          <p style="margin:0; font-size:36px; font-weight:700; letter-spacing:8px; color:#f97316; font-family:'Courier New',monospace;">
            ${r}
          </p>
        </div>
        
        <p style="margin:24px 0 0; color:#a1a1aa; font-size:13px; text-align:center;">
          ⏰ This code expires in ${o} minutes<br>
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
</html>`,tags:["otp-verification"]})}async function s(e){let{to:t,userName:r,amount:a,currency:o="INR",planName:s,orderId:i,status:l}=e,d="completed"===l,p=d?`Payment Confirmed ✅ ₹${a} for ${s}`:`Payment Update: ${s}`,c=d?"#10b981":"#f59e0b";return n({to:t,subject:p,htmlContent:`
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
</head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; padding:20px;">
    
    <tr>
      <td style="background:${c}; padding:30px; border-radius:16px 16px 0 0; text-align:center;">
        <h1 style="margin:0; color:white; font-size:28px;">${d?"✅":"⏳"} Payment ${d?"Confirmed":"Update"}</h1>
        <p style="margin:8px 0 0; color:rgba(255,255,255,0.9);">
          ${d?"Thank you for your payment!":"Your payment is being processed"}
        </p>
      </td>
    </tr>
    
    <tr>
      <td style="background:white; padding:40px 30px; border:1px solid #e4e4e7;">
        
        <p style="margin:0 0 24px; color:#52525b;">
          Hi${r?`, ${r}`:""},
        </p>
        
        <!-- Payment Details -->
        <div style="background:#fafafa; border-radius:12px; padding:24px; margin:20px 0;">
          
          <table style="width:100%; border-collapse:collapse;">
            <tr>
              <td style="padding:12px 0; color:#71717a; font-size:14px;">Plan</td>
              <td style="padding:12px 0; text-align:right; color:#18181b; font-weight:600;">${s}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Amount</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right; color:#18181b; font-weight:700; font-size:18px;">₹${a.toLocaleString()}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Order ID</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right; color:#18181b; font-family:monospace; font-size:13px;">${i}</td>
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
        
        ${d?`
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
</html>`,tags:["payment",`payment-${l}`,s.toLowerCase()]})}e.s(["sendOtpEmail",0,o,"sendPaymentReceipt",0,s])},11562,e=>{"use strict";var t=e.i(47909),r=e.i(74017),a=e.i(96250),n=e.i(59756),o=e.i(61916),s=e.i(74677),i=e.i(69741),l=e.i(16795),d=e.i(87718),p=e.i(95169),c=e.i(47587),u=e.i(66012),x=e.i(70101),g=e.i(26937),m=e.i(10372),f=e.i(93695);e.i(52474);var h=e.i(220),y=e.i(89171),b=e.i(42616);let v=new Map;async function w(e){try{let{email:t}=await e.json();if(!t||!t.includes("@"))return y.NextResponse.json({error:"validation_error",message:"Valid email address is required"},{status:400});let r=t.toLowerCase().trim(),a=v.get(r);if(a&&a.expiresAt>new Date){let e=Math.ceil((a.expiresAt.getTime()-Date.now())/1e3/60);if(a.attempts>=3)return y.NextResponse.json({error:"rate_limited",message:`Too many requests. Try again in ${e} minutes.`},{status:429})}let n=Math.floor(1e5+9e5*Math.random()).toString(),o=new Date(Date.now()+6e5);v.set(r,{code:n,expiresAt:o,attempts:(a?.attempts||0)+1}),console.log(`[OTP] Generated for ${r}: ${n} (expires ${o.toISOString()})`);let s=await (0,b.sendOtpEmail)({to:r,otpCode:n,expiryMinutes:10});if(!s.success)return y.NextResponse.json({error:"send_failed",message:s.error||"Failed to send OTP email"},{status:500});return y.NextResponse.json({success:!0,message:"OTP sent successfully",expires_in:600})}catch(e){return console.error("[OTP Send Error]:",e),y.NextResponse.json({error:"internal_error",message:"Failed to send OTP"},{status:500})}}e.s(["POST",0,w],68879);var R=e.i(68879);let E=new t.AppRouteRouteModule({definition:{kind:r.RouteKind.APP_ROUTE,page:"/api/verification/send-otp/route",pathname:"/api/verification/send-otp",filename:"route",bundlePath:""},distDir:".next",relativeProjectDir:"",resolvedPagePath:"[project]/src/app/api/verification/send-otp/route.ts",nextConfigOutput:"standalone",userland:R,...{}}),{workAsyncStorage:C,workUnitAsyncStorage:A,serverHooks:P}=E;async function T(e,t,a){a.requestMeta&&(0,n.setRequestMeta)(e,a.requestMeta),E.isDev&&(0,n.addRequestMeta)(e,"devRequestTimingInternalsEnd",process.hrtime.bigint());let y="/api/verification/send-otp/route";y=y.replace(/\/index$/,"")||"/";let b=await E.prepare(e,t,{srcPage:y,multiZoneDraftMode:!1});if(!b)return t.statusCode=400,t.end("Bad Request"),null==a.waitUntil||a.waitUntil.call(a,Promise.resolve()),null;let{buildId:v,deploymentId:w,params:R,nextConfig:C,parsedUrl:A,isDraftMode:P,prerenderManifest:T,routerServerContext:O,isOnDemandRevalidate:k,revalidateOnlyGenerated:S,resolvedPathname:$,clientReferenceManifest:N,serverActionsManifest:_}=b,I=(0,i.normalizeAppPath)(y),j=!!(T.dynamicRoutes[I]||T.routes[$]),M=async()=>((null==O?void 0:O.render404)?await O.render404(e,t,A,!1):t.end("This page could not be found"),null);if(j&&!P){let e=!!T.routes[$],t=T.dynamicRoutes[I];if(t&&!1===t.fallback&&!e){if(C.adapterPath)return await M();throw new f.NoFallbackError}}let q=null;!j||E.isDev||P||(q="/index"===(q=$)?"/":q);let U=!0===E.isDev||!j,D=j&&!U;_&&N&&(0,s.setManifestsSingleton)({page:y,clientReferenceManifest:N,serverActionsManifest:_});let H=e.method||"GET",z=(0,o.getTracer)(),F=z.getActiveScopeSpan(),B=!!(null==O?void 0:O.isWrappedByNextServer),L=!!(0,n.getRequestMeta)(e,"minimalMode"),K=(0,n.getRequestMeta)(e,"incrementalCache")||await E.getIncrementalCache(e,C,T,L);null==K||K.resetRequestCache(),globalThis.__incrementalCache=K;let V={params:R,previewProps:T.preview,renderOpts:{experimental:{authInterrupts:!!C.experimental.authInterrupts},cacheComponents:!!C.cacheComponents,supportsDynamicResponse:U,incrementalCache:K,cacheLifeProfiles:C.cacheLife,waitUntil:a.waitUntil,onClose:e=>{t.on("close",e)},onAfterTaskError:void 0,onInstrumentationRequestError:(t,r,a,n)=>E.onRequestError(e,t,a,n,O)},sharedContext:{buildId:v,deploymentId:w}},Y=new l.NodeNextRequest(e),G=new l.NodeNextResponse(t),W=d.NextRequestAdapter.fromNodeNextRequest(Y,(0,d.signalFromNodeResponse)(t));try{let n,s=async e=>E.handle(W,V).finally(()=>{if(!e)return;e.setAttributes({"http.status_code":t.statusCode,"next.rsc":!1});let r=z.getRootSpanAttributes();if(!r)return;if(r.get("next.span_type")!==p.BaseServerSpan.handleRequest)return void console.warn(`Unexpected root span type '${r.get("next.span_type")}'. Please report this Next.js issue https://github.com/vercel/next.js`);let a=r.get("next.route");if(a){let t=`${H} ${a}`;e.setAttributes({"next.route":a,"http.route":a,"next.span_name":t}),e.updateName(t),n&&n!==e&&(n.setAttribute("http.route",a),n.updateName(t))}else e.updateName(`${H} ${y}`)}),i=async n=>{var o,i;let l=async({previousCacheEntry:r})=>{try{if(!L&&k&&S&&!r)return t.statusCode=404,t.setHeader("x-nextjs-cache","REVALIDATED"),t.end("This page could not be found"),null;let o=await s(n);e.fetchMetrics=V.renderOpts.fetchMetrics;let i=V.renderOpts.pendingWaitUntil;i&&a.waitUntil&&(a.waitUntil(i),i=void 0);let l=V.renderOpts.collectedTags;if(!j)return await (0,u.sendResponse)(Y,G,o,V.renderOpts.pendingWaitUntil),null;{let e=await o.blob(),t=(0,x.toNodeOutgoingHttpHeaders)(o.headers);l&&(t[m.NEXT_CACHE_TAGS_HEADER]=l),!t["content-type"]&&e.type&&(t["content-type"]=e.type);let r=void 0!==V.renderOpts.collectedRevalidate&&!(V.renderOpts.collectedRevalidate>=m.INFINITE_CACHE)&&V.renderOpts.collectedRevalidate,a=void 0===V.renderOpts.collectedExpire||V.renderOpts.collectedExpire>=m.INFINITE_CACHE?void 0:V.renderOpts.collectedExpire;return{value:{kind:h.CachedRouteKind.APP_ROUTE,status:o.status,body:Buffer.from(await e.arrayBuffer()),headers:t},cacheControl:{revalidate:r,expire:a}}}}catch(t){throw(null==r?void 0:r.isStale)&&await E.onRequestError(e,t,{routerKind:"App Router",routePath:y,routeType:"route",revalidateReason:(0,c.getRevalidateReason)({isStaticGeneration:D,isOnDemandRevalidate:k})},!1,O),t}},d=await E.handleResponse({req:e,nextConfig:C,cacheKey:q,routeKind:r.RouteKind.APP_ROUTE,isFallback:!1,prerenderManifest:T,isRoutePPREnabled:!1,isOnDemandRevalidate:k,revalidateOnlyGenerated:S,responseGenerator:l,waitUntil:a.waitUntil,isMinimalMode:L});if(!j)return null;if((null==d||null==(o=d.value)?void 0:o.kind)!==h.CachedRouteKind.APP_ROUTE)throw Object.defineProperty(Error(`Invariant: app-route received invalid cache entry ${null==d||null==(i=d.value)?void 0:i.kind}`),"__NEXT_ERROR_CODE",{value:"E701",enumerable:!1,configurable:!0});L||t.setHeader("x-nextjs-cache",k?"REVALIDATED":d.isMiss?"MISS":d.isStale?"STALE":"HIT"),P&&t.setHeader("Cache-Control","private, no-cache, no-store, max-age=0, must-revalidate");let p=(0,x.fromNodeOutgoingHttpHeaders)(d.value.headers);return L&&j||p.delete(m.NEXT_CACHE_TAGS_HEADER),!d.cacheControl||t.getHeader("Cache-Control")||p.get("Cache-Control")||p.set("Cache-Control",(0,g.getCacheControlHeader)(d.cacheControl)),await (0,u.sendResponse)(Y,G,new Response(d.value.body,{headers:p,status:d.value.status||200})),null};B&&F?await i(F):(n=z.getActiveScopeSpan(),await z.withPropagatedContext(e.headers,()=>z.trace(p.BaseServerSpan.handleRequest,{spanName:`${H} ${y}`,kind:o.SpanKind.SERVER,attributes:{"http.method":H,"http.target":e.url}},i),void 0,!B))}catch(t){if(t instanceof f.NoFallbackError||await E.onRequestError(e,t,{routerKind:"App Router",routePath:I,routeType:"route",revalidateReason:(0,c.getRevalidateReason)({isStaticGeneration:D,isOnDemandRevalidate:k})},!1,O),j)throw t;return await (0,u.sendResponse)(Y,G,new Response(null,{status:500})),null}}e.s(["handler",0,T,"patchFetch",0,function(){return(0,a.patchFetch)({workAsyncStorage:C,workUnitAsyncStorage:A})},"routeModule",0,E,"serverHooks",0,P,"workAsyncStorage",0,C,"workUnitAsyncStorage",0,A],11562)}];

//# sourceMappingURL=%5Broot-of-the-server%5D__0jq41pe._.js.map