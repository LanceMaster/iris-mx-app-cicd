## 1. 파이썬 환경변수 docker-compose 업데이트 

#### 📂 디렉토리 및 파일 구조

- 아래와 같은 구조로 프로젝트 디렉토리와 파일 구성.

```bash
.
├── docker-compose.base.yml   # 모든 환경에서 공통으로 사용할 템플릿
├── update_compose.py         # Python 스크립트
├── run_update.sh             # Bash 실행 스크립트
├── dev/
│   └── app.dev.env               # 개발 환경 변수 파일
├── qa/
│   └── app.qa.env                # QA 환경 변수 파일
└── prd/
    └── app.prd.env               # 운영 환경 변수 파일

```

## 2. Jenkins 공통함수

```bash
// =============================================================================
//  원격 빌드 서버 정보 (Remote Build Server Info) 
// =============================================================================
def REMOTE_SERVER = [
            name: "",
            host: "",
            user: "",
            identityFile: "",      
            allowAnyHosts: true // 처음 연결 시 호스트 키 확인을 건너뛰는 옵션
        ]


def Map<String, Object> initConfigEnv = [:]  //환경변수

// =============================================================================
//  공통함수
// 1.단일 따옴표 안전 이스케이프 : ' -> '"'"' 
// =============================================================================
def toShEscape = {String v ->    
    if (v == null) return "''"    
    def vEx =  "'" + v.replace("'", "'\"'\"'") + "'" 
   // echo "jenkins toShEscape: ${vEx}"
    return vEx
}

// =============================================================================
//  공통함수
// 2.env 맵을  export 구문(AND 체인)으로 변환
// =============================================================================
def toExportChain = {Map<String, Object> envMap -> 
     envMap.collect { k,v -> "export ${k}=" +
     toShEscape(v?.toString() ?: "")}.join(' && ')    
}

// =============================================================================
//  공통함수
// 3.오른쪽 공백 제거
// =============================================================================
def rtrim = {String rt -> 
   if (rt == null) return ''
   //줄 끝의 공백/탭 등만 제거
   return rt.replaceAll(/\s+$/,'')
}
// =============================================================================
//  공통함수
// 3.멀티라인 명령 -> 빈줄/주석 제거하고 원래 줄 구조 유지
// =============================================================================
def toFilteredLiner = {String cmd -> 
   cmd.readLines()
      .collect { line -> rtrim(line) }   //끝 공백만 제거
      .findAll { line -> 
                 def t = line.trim()
                 return t && !t.startsWith('#')     //빈줄/주석 제외
               }
               .join('\n')     //줄바꿈 
}
 
 
// =============================================================================
//  공통함수
// 4.sshRunAlwaysHeredoc(host,user,credId,rawCmd, extraEnv = [:], sudoE = false)
// rawCmd : 멀티라인 (자동  && 체인)
// extraEnv : export 앞에 주입
// sudoE : true 면 'sudo -E bash -lc' 로 실행
// =============================================================================
def sshRunAlwaysHeredoc = {String rawCmd,Map<String,Object> extraEnv = [:], boolean sudoE = false  ->
    
    // echo "jenkins env: ${sshconfig}"
    //기본 env + 추가 envi
    // 공통 환경변수 선언 
    //APP_PATH : env.APP_PATH,
    //TAG : env.TAG
   Map<String,Object> mergedEnv = [
        APP_NAME : "${env.APP_NAME}",
        APP_VERSION : "${env.APP_VERSION}",
		DEPLOY_ENV : "${env.DEPLOY_ENV}" ,
        BRANCH_NAME : "${env.BRANCH_NAME}",
        GITHUB_URL : "${env.GITHUB_URL}",
        DOCKER_ENDPOINT : "${env.DOCKER_ENDPOINT}",
        DOCKER_HOST_ENDPOINT : "${env.DOCKER_HOST_ENDPOINT}",   
        DOCKER_DIR_PREFIX : "${env.DOCKER_DIR_PREFIX}",
        APP_PORT : "${env.APP_PORT}",
        RUNTIME_PORT : "${env.RUNTIME_PORT}",
        BUILD_MODE : "${env.BUILD_MODE}",
        TAG_CNT_LIMIT : "${env.TAG_CNT_LIMIT}",
        APP_WRK_PATH : "${env.APP_WRK_PATH}",
		APP_BRANCH_PATH : "${env.APP_BRANCH_PATH}"
   ] +  extraEnv
 
   String exportChain = toExportChain(mergedEnv)   
   String bashPrefix = sudoE ? 'sudo -E bash -lc' : 'bash -lc'
   def filterRawCmd = toFilteredLiner(rawCmd)
   String scriptBody

   // 제어문 : heredoc으로 안전하게 전달 (월격에서 변수 확장)
   scriptBody = """
        ${bashPrefix} ${toShEscape("""\
        set -eo pipefail
        ${exportChain}
        TMPDIR=\$(mktemp -d /tmp/jenkins_cmd_XXXXXXXXXXXX)
        trap 'rm -rf "\$TMPDIR"' EXIT INT TERM
cat <<'EOS' > "\$TMPDIR/tmprun.sh"
#!/bin/bash
set -eo pipefail
${filterRawCmd}
EOS
         chmod +x "\$TMPDIR/tmprun.sh"
         "\$TMPDIR/tmprun.sh"
         """.stripIndent())}
     """.trim()
 
   
   return scriptBody 
} 

// =============================================================================
//  원격 실행 함수 (Remote Execution Function)
// =============================================================================
/**
 * 원격 서버에서 셸 커맨드를 실행.
 * @param config Map: 실행 설정값
 * - remote: sshCommand에 전달할 원격 서버 정보 (name, host, user, credentialsId 등)
 * - command: 원격 서버에서 실행할 셸 스크립트 문자열
 */
def remoteExecute(Map config) {
    // sshCommand 스텝을 사용하여 원격지에서 스크립트 실행
      echo "--- Starting ssh env configation ---"
    config.remote.name = "${APP_NODE_HOSTNAME}"
    config.remote.host ="${APP_NODE_IP}"
    config.remote.user = "${SSH_USER}"
    config.remote.identityFile = "${SSH_KEY}"
   // config.remote.credentialsId =  "${SSH_CREDENTIAL_ID}"
    echo "--- End ssh env configation ---"
    sshCommand remote: config.remote, command: config.command
}

// =============================================================================
//  원격 실행 함수 (Remote Execution Function)
// =============================================================================
/**
 * 원격 서버에서 셸 커맨드를 실행하고 그 결과를 반환합니다.
 * @param config Map: 실행 설정값
 * - remote: sshCommand에 전달할 원격 서버 정보 (name, host, user, credentialsId 등)
 * - command: 원격 서버에서 실행할 셸 스크립트 문자열
 * @return String: 원격 명령어의 표준 출력(stdout) 결과
 */
def remoteExecuteAndGetOutput(Map config) {

    echo "--- Starting ssh env configation ---"
    config.remote.name = "${APP_NODE_HOSTNAME}"
    config.remote.host ="${APP_NODE_IP}"
    config.remote.user = "${SSH_USER}"
    config.remote.identityFile = "${SSH_KEY}"
    //config.remote.credentialsId =  "${SSH_CREDENTIAL_ID}"
    echo "--- End ssh env configation ---"

    // returnStdout: true 옵션으로 명령어 실행 결과를 반환받음
    return sshCommand (remote: config.remote, command: config.command, returnStdout: true)
}

```

## 3. SSH credentials 값 처리 방법 

```script

        // 젠킨스 credentials 추출
        stage('Deploy and Verify') {
            steps {
              withCredentials([     
                              sshUserPrivateKey(credentialsId: '<Jenkins Credentials>', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER') ,                  
                              string(credentialsId: '<Jenkins Credentials>', variable: 'LIC_KEY')
                   ]) { 
                script {


                           // === 1. Jenkins에서 전달된 환경 변수 설정 === 
                         echo "--- Starting Jenkins env configation ---"
                          //# Jenkins 변수를 셸 변수로 설정
                          initConfigEnv = [    
                                APP_COMPOSE_PATH : "${env.APP_COMPOSE_PATH}"                                                      
                          ]
                        // echo "jenkins env: ${initConfigEnv}"
                         echo "--- End Jenkins env configation ---" 

                        echo "--- Running Deploy and Verify ---"

                        def envContent = """
LICENSE_KEY='${LIC_KEY}'                           
                        """
                        
                        //원자적쓰기 (base64 경유)
                        //byte[] bytes = envContent.getBytes('UTF-8')
                        //String bs64 = bytes.encodeBase64().toString()
                         //writeFile file: 'env.tmp', text: envContent

                        def remoteEnvScript = """
                            #!/bin/bash
                            # -e: 오류 발생 시 즉시 중단
                            # -u: 정의되지 않은 변수 사용 시 오류
                            # -x: 실행되는 모든 명령어를 출력
                            # -o pipefail: 파이프라인의 어느 한 곳이라도 실패하면 전체 실패 처리
                            set -exo pipefail 

                            cd \${APP_COMPOSE_PATH}        
                            echo "--- Starting env on Remote Server ---"
                            
                            umask 077 
cat > .env.tmp <<'EOT'
${envContent}
EOT

                             sudo mv -f .env.tmp  .env
                             sudo chmod 600 .env

                            echo "--- Remote env Finished Successfully ---"

                        """    

                         // try-catch 블록으로 원격 실행 실패 시 롤백 로직을 처리
                        try {
                            // remoteExecute 함수를 호출하여 원격 서버에서 스크립트 실행 
                             remoteExecute(remote: REMOTE_SERVER, command: sshRunAlwaysHeredoc(remoteEnvScript,initConfigEnv,false))           
                             initConfigEnv = [:]  //환경변수
                        } catch (e) { 
                            // 원본 에러를 다시 발생시켜 빌드를 최종적으로 실패 처리
                            throw e
                        }   
                       
                    }
                }
            }
        }

```


## 특정 스케줄링 

```bash

SCHEDULED_EVENTS=true
MXRUNTIME_ScheduledEventExecution='SPECIFIED'
MXRUNTIME_MyScheduledEvents="SAML20.SE_LogCleanUp,SAML20.SE_SynchronizeIdPMetadata"

```

#### 1. 스케줄러를 켜는 설정 
Mendix Docker Buildpack은 SCHEDULED_EVENTS 변수를 읽어서 컨테이너에서 스케줄러를 켤지 여부를 판단
기본적으로는 false 설정되어 스케줄러 비활성화, true 면 스케줄러를 활성화

Mendix Runtime 내부설정(Custom Runtime Settings)을 환경변수로 주입해야함
특정 이벤트만을 실행하는경우 ScheduledEventExecution 값을 SPECIFIED 변경 MyScheduledEvents 에 실행할 이벤트 목록 기입

#### 2. MXRUNTIME_ScheduledEventExecution
- 스케줄러가 어떤 이벤트를 실행할지 결정하는 정책
- VALUE : ALL :  모든이벤트 실행 (기본값)
          NONE : 아무실행도 실행하지 않음 
          SPECIFIED : MyScheduledEvents 에 정의된 목록만 실행

#### 3. MXRUNTIME_MyScheduledEvents
- SPECIFIED 모드일때 실행할 화이트 리스트 
- 여러개의 스케줄이벤트 실행시 콤마(,)로 구분 
- 주의 : 대소문자를 정확히 지켜야하고, 공백이 들어가지 않아야함.

