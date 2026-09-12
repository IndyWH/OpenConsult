# Security policy

## What this project is

OpenConsult is a research and education prototype. It is not a medical device, it has had no regulatory assessment, and it must never be used with real patients or real patient data. Every consultation used in its development is synthetic — scripted or acted.

It is built to run on one machine on a private network, with no inbound access from the internet. Exposing it to the public internet is not a supported configuration, and the design does not defend against it.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Use GitHub's private reporting instead. Go to the Security tab of this repository and click "Report a vulnerability". That opens a thread visible only to you and me.

I am a practising GP and I maintain this in my own time, so I cannot offer a fixed response time. I aim to acknowledge a report within 14 days. If it is valid I will tell you what I plan to do and roughly when, and I will credit you when the fix is published unless you would rather I did not.

There is no bug bounty and no payment.

## Supported versions

The current main branch and the most recent release. Fixes are not backported.

## In scope

Anything in this repository's own code. That includes authentication and session handling, the role boundaries enforced server side, the audit trail, the review and approval path, input handling and output escaping, the database layer, the API, the audio and file handling, and the packaging in Dockerfile and docker-compose.yml.

## Out of scope

The vendored face engine under vendor/ is pinned upstream code. Report a problem there to the upstream project, and tell me if it also affects OpenConsult.

Model weights, and the services that serve them, are out of scope. So are third-party dependencies: report those to the project concerned, and tell me if the way OpenConsult uses them makes something exploitable here.

Anything that depends on the app being exposed to the public internet is out of scope, for the reason given above.

## What has already been found

An independent audit in July 2026 raised twelve issues, one of them critical. What they were and what was done about them is written up in help/08-security.md. I would rather hear what that audit missed than hear that it looked thorough.
