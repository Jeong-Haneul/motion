# VMC 기록 — 라벨에서 만든 자세를 어떻게 담나

출처: 프로토콜 저장소 `sh-akira/VirtualMotionCaptureProtocol`의 `docs/marionette-spec.markdown`, `docs/performer-spec.markdown`(프로토콜 **v3.1**)과 `sample/VRM1/SampleBonesSendBundle.cs`(참조 송신 코드). 직접 읽고 확인한 내용이다.

## 1. 기록되는 데이터 (Performer → Marionette)

| 메시지 | 인자 | 비고 |
|---|---|---|
| `/VMC/Ext/Root/Pos` | `"root"` p.xyz q.xyzw (v2.1부터 s.xyz o.xyz 추가) | 모델 루트의 **절대** 자세 |
| `/VMC/Ext/Bone/Pos` | 본 이름, p.xyz, q.xyzw | 본의 **로컬** 자세. 이름은 Unity `HumanBodyBones` 이름(`Hips`, `LeftUpperArm` …). **모든 본을 보낸다**(손가락·눈 포함, `LastBone` 제외) |
| `/VMC/Ext/Blend/Val` + `/VMC/Ext/Blend/Apply` | 표정 이름, 값 | 값을 모두 보낸 뒤 `Apply`. **대소문자 구분** |
| `/VMC/Ext/OK` | loaded (+ 보정 상태 등) | 본·표정이 송신 중인지 |
| `/VMC/Ext/T` | 송신 쪽 상대 시간(float) | |

- 표정 이름은 **VRM0 방식이 필수**다: `Joy` `Angry` `Sorrow` `Fun` `A` `I` `U` `E` `O` `Blink_L` `Blink_R`. VRM1 방식(`happy` `blinkLeft` …)은 선택 사항.
- 한 번에 보내는 UDP 묶음(bundle)은 **1500바이트 이내**여야 한다. 본이 많으면 여러 묶음으로 나눈다. (앞서 만든 모의 송신은 1,948바이트를 한 묶음으로 보냈으므로 이 규칙을 어겼다.)
- 규격은 **라이브 스트림**이고 파일 형식은 정의하지 않는다. 기록은 따로 정해야 한다.
- 문서에는 좌표계가 명시되어 있지 않다. 참조 코드가 Unity의 `localPosition/localRotation`을 그대로 보내므로 Unity 기준(왼손 좌표계)이라고 보는 것이 맞지만, 문서의 문장으로는 확인하지 못했다.

## 2. 라벨 축이 기록에 어떻게 대응하나

**10축과 확장 축의 값이 VMC 스트림의 어디에 나타나는지**만 보여 준다. 스트림에 안 나타나는 축도 **라벨로 그대로 남는다**(클립에 붙는 라벨).

| 라벨 축 | 기록되는 곳 |
|---|---|
| 대분류, 상하, 몸통 | `Bone/Pos` 회전(Hips·Spine·Chest·UpperChest) + `Root/Pos`(높이, 도립·눕기는 루트 회전) |
| 좌우 | 스트림에 직접 나타나지 않는다. 쪽별 팔·다리 값이 왼/오른 본 회전으로 나타나고, 라벨로 남는다 |
| 팔(쪽별) | `LeftShoulder/UpperArm/LowerArm/Hand`, `RightShoulder/UpperArm/LowerArm/Hand` |
| 다리(쪽별) | `LeftUpperLeg/LowerLeg/Foot/Toes`, `RightUpperLeg/LowerLeg/Foot/Toes` |
| 머리·시선 | `Neck`·`Head`·`LeftEye`·`RightEye` 본 |
| 표정 | 표정 프리셋: 미소·웃음 → `Joy`(+`A`), 화남 → `Angry`, 슬픔 → `Sorrow`, 놀람 → `A`+`O`, 윙크 → `Blink_L` 또는 `Blink_R`, 눈 감음 → `Blink_L`+`Blink_R` (VRM0 이름) |
| 남녀, 노소 | 스트림에는 안 나타난다. **라벨로 남고**, 자세를 만들 때 비어 있는 축의 사전값으로 쓰인다 |
| (확장) 손 모양 | 손가락 본(Thumb·Index·Middle·Ring·Little) |
| (확장) 접촉, 긴장 | 스트림에는 안 나타난다. 라벨로 남는다 |

- 스트림에는 `앉기`가 의자 없이 앉은 자세로, `짚기`·`기대기`가 바닥·벽 없는 자세로 나타난다. 이 정보는 라벨에 남는다.
- 라벨과 자세를 한 스트림에 같이 두려면 규격에 있는 **스루(Thru) 메시지** `/VMC/Thru/<이름>/<이름> (string)`을 쓸 수 있다. 수신 쪽이 처리하지 않고 그대로 중계하는 확장용 메시지이다. 별도 파일로 두는 방법도 있다.

## 3. 정해야 할 것

1. **어느 본 자세로 기록하나.** 규격은 VRM1에서 정규화되지 않은 **원래 본**의 자세를 권장하고, 정규화 본 전송은 금지하지 않지만 비권장(기본 꺼짐)이다. 원래 본의 로컬 자세는 아바타마다 다르므로, 기준이 될 **아바타(VRM) 하나**를 정해야 한다.
2. **기록 파일 형식.** 예: 시각 + 주소 + 인자를 한 줄씩 담은 JSON Lines.
3. **라벨을 어디에 두나.** 스트림 안(`Thru`)인지, 클립마다 따로 붙는 파일인지.
