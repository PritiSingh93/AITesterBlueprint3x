AI3X_004_API_Contract_Validator,

We are going to give you a GET request, a simple GET request, and we are also going to give you a JSON schema. What you need to do is use the API component to make the request. Whatever the JSON schema is there, you need to verify it with that response.
is they are matching via the openRouter model deepseek v4 flash. 
 

curl Request GET - 
https://gorest.co.in/public/v2/users


Response
[{"id":8509253,"name":"Mr. Gitanjali Sethi","email":"mr_sethi_gitanjali@gislason-schinner.test","gender":"male","status":"active"},{"id":8509251,"name":"Sucheta Kaniyar DDS","email":"dds_kaniyar_sucheta@bruen-grady.test","gender":"female","status":"active"},{"id":8509250,"name":"Bhupati Pothuvaal","email":"pothuvaal_bhupati@hilll-mitchell.test","gender":"female","status":"active"},{"id":8509249,"name":"Anandamayi Varrier","email":"anandamayi_varrier@feil.example","gender":"female","status":"inactive"},{"id":8509248,"name":"Rep. Tara Joshi","email":"tara_joshi_rep@schneider-mosciski.test","gender":"female","status":"active"},{"id":8509247,"name":"Dwaipayana Mehrotra","email":"dwaipayana_mehrotra@hane-anderson.example","gender":"male","status":"active"},{"id":8509246,"name":"Deeptimoyee Dwivedi","email":"deeptimoyee_dwivedi@fahey-price.example","gender":"male","status":"inactive"},{"id":8509245,"name":"Miss Kamalesh Tandon","email":"miss_tandon_kamalesh@champlin.test","gender":"female","status":"inactive"},{"id":8509243,"name":"Mrs. Shakuntala Ahluwalia","email":"shakuntala_ahluwalia_mrs@bahringer-mclaughlin.example","gender":"male","status":"active"},{"id":8509242,"name":"Gandharva Arora DC","email":"gandharva_dc_arora@reynolds-rice.test","gender":"female","status":"active"}]


JSON Schema
{
  "$schema": "http://json-schema.org/draft-04/schema#",
  "type": "array",
  "items": [
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    },
    {
      "type": "object",
      "properties": {
        "id": {
          "type": "integer"
        },
        "name": {
          "type": "string"
        },
        "email": {
          "type": "string"
        },
        "gender": {
          "type": "string"
        },
        "status": {
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "email",
        "gender",
        "status"
      ]
    }
  ]
}